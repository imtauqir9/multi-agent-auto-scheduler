"""
SQLite persistence layer (thread-safe).

Tables
------
agent_runs     : one row per agent execution (status, duration, summary).
resource_stats : periodic CPU/RAM/disk snapshots from the orchestrator.
scheduler_log  : LLM scheduling decisions (queued / started / finished / throttled).
agent_outputs  : structured results an agent wants to surface on the dashboard
                 (e.g. classified emails, stock rows, calendar suggestions).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

from config import settings

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    agent      TEXT NOT NULL,
    status     TEXT NOT NULL,           -- success | error | skipped
    summary    TEXT,
    duration_s REAL,
    started_at REAL NOT NULL,
    ended_at   REAL
);

CREATE TABLE IF NOT EXISTS resource_stats (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_pct   REAL,
    ram_pct   REAL,
    disk_pct  REAL,
    ts        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduler_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    agent    TEXT NOT NULL,
    event    TEXT NOT NULL,             -- queued | started | finished | throttled | deadlock_avoided
    detail   TEXT,
    ts       REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_outputs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    agent    TEXT NOT NULL,
    title    TEXT,
    body     TEXT,
    meta     TEXT,
    ts       REAL NOT NULL
);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript(SCHEMA)


# ----------------------------------------------------------------------- #
# Writers
# ----------------------------------------------------------------------- #
def start_run(agent: str) -> int:
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO agent_runs (agent, status, started_at) VALUES (?, 'running', ?)",
            (agent, time.time()),
        )
        return cur.lastrowid


def finish_run(run_id: int, status: str, summary: str, started_at: float) -> None:
    now = time.time()
    with _LOCK, _connect() as conn:
        conn.execute(
            "UPDATE agent_runs SET status=?, summary=?, duration_s=?, ended_at=? WHERE id=?",
            (status, summary, round(now - started_at, 2), now, run_id),
        )


def log_resource(cpu: float, ram: float, disk: float) -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO resource_stats (cpu_pct, ram_pct, disk_pct, ts) VALUES (?,?,?,?)",
            (cpu, ram, disk, time.time()),
        )
        # keep only the most recent 500 samples
        conn.execute(
            "DELETE FROM resource_stats WHERE id NOT IN "
            "(SELECT id FROM resource_stats ORDER BY id DESC LIMIT 500)"
        )


def log_schedule(agent: str, event: str, detail: str = "") -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO scheduler_log (agent, event, detail, ts) VALUES (?,?,?,?)",
            (agent, event, detail, time.time()),
        )


def save_output(agent: str, title: str, body: str, meta: str = "") -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            "INSERT INTO agent_outputs (agent, title, body, meta, ts) VALUES (?,?,?,?,?)",
            (agent, title, body, meta, time.time()),
        )


# ----------------------------------------------------------------------- #
# Readers (used by the dashboard API)
# ----------------------------------------------------------------------- #
def _rows(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    with _LOCK, _connect() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM agent_runs ORDER BY id DESC LIMIT ?", (limit,))


def recent_resources(limit: int = 60) -> list[dict[str, Any]]:
    return list(reversed(_rows("SELECT * FROM resource_stats ORDER BY id DESC LIMIT ?", (limit,))))


def recent_schedule(limit: int = 30) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM scheduler_log ORDER BY id DESC LIMIT ?", (limit,))


def recent_outputs(limit: int = 30) -> list[dict[str, Any]]:
    return _rows("SELECT * FROM agent_outputs ORDER BY id DESC LIMIT ?", (limit,))
