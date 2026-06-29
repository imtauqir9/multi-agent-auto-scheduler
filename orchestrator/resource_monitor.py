"""
System resource monitor (CPU / RAM / disk) using psutil.

Runs on a background thread, snapshots the machine every few seconds, persists
samples to SQLite, and exposes the latest reading plus a throttle decision the
LLM scheduler consults before dispatching a job.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import psutil

from config import settings
from core import database as db

log = logging.getLogger("resource_monitor")


@dataclass
class ResourceSnapshot:
    cpu_pct: float
    ram_pct: float
    disk_pct: float
    ts: float

    def as_dict(self) -> dict:
        return {
            "cpu_pct": round(self.cpu_pct, 1),
            "ram_pct": round(self.ram_pct, 1),
            "disk_pct": round(self.disk_pct, 1),
            "ts": self.ts,
        }


class ResourceMonitor:
    def __init__(self, interval_s: int = 3) -> None:
        self.interval_s = interval_s
        self._latest = ResourceSnapshot(0.0, 0.0, 0.0, time.time())
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # Prime psutil's CPU counter (first call always returns 0.0).
        psutil.cpu_percent(interval=None)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="resource-monitor", daemon=True)
        self._thread.start()
        log.info("Resource monitor started (interval=%ss)", self.interval_s)

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            snap = self.sample()
            db.log_resource(snap.cpu_pct, snap.ram_pct, snap.disk_pct)
            if snap.disk_pct >= settings.disk_alert_percent:
                log.warning("Disk usage high: %.1f%%", snap.disk_pct)
            self._stop.wait(self.interval_s)

    def sample(self) -> ResourceSnapshot:
        snap = ResourceSnapshot(
            cpu_pct=psutil.cpu_percent(interval=None),
            ram_pct=psutil.virtual_memory().percent,
            disk_pct=psutil.disk_usage(str(settings.base_dir)).percent,
            ts=time.time(),
        )
        self._latest = snap
        return snap

    @property
    def latest(self) -> ResourceSnapshot:
        return self._latest

    def is_overloaded(self) -> tuple[bool, str]:
        """
        Decide whether the machine is too busy to start a new LLM job.
        Returns (overloaded, reason).
        """
        s = self._latest
        if s.cpu_pct >= settings.cpu_throttle_percent:
            return True, f"CPU at {s.cpu_pct:.0f}% (limit {settings.cpu_throttle_percent}%)"
        if s.ram_pct >= settings.ram_throttle_percent:
            return True, f"RAM at {s.ram_pct:.0f}% (limit {settings.ram_throttle_percent}%)"
        return False, ""
