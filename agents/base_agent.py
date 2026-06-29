"""
BaseAgent — common lifecycle for every specialized agent.

Subclasses implement `execute()` and return a short human-readable summary
string. The base class handles run bookkeeping (timing, status, DB logging) so
the orchestrator and dashboard get consistent telemetry for free.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from core import database as db


@dataclass
class BaseAgent:
    name: str
    description: str
    priority: int = 5                      # lower = scheduled first
    resources: list[str] = field(default_factory=list)  # extra named locks
    last_status: str = "idle"
    last_summary: str = ""
    last_run_ts: float = 0.0

    # ------------------------------------------------------------------ #
    def execute(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    def run(self) -> str:
        """Wrap execute() with timing, status and persistence."""
        logging.getLogger(self.name).info("Starting run")
        run_id = db.start_run(self.name)
        started = time.time()
        try:
            summary = self.execute() or "done"
            self.last_status = "success"
        except Exception as exc:  # noqa: BLE001 - we record every failure
            summary = f"{type(exc).__name__}: {exc}"
            self.last_status = "error"
            logging.getLogger(self.name).exception("Run failed")
        finally:
            self.last_run_ts = time.time()
            self.last_summary = summary
        db.finish_run(run_id, self.last_status, summary, started)
        return summary

    # ------------------------------------------------------------------ #
    def describe(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "resources": self.resources,
            "last_status": self.last_status,
            "last_summary": self.last_summary,
            "last_run_ts": self.last_run_ts,
        }
