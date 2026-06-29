"""
Main Orchestrator.

Owns the resource monitor and the LLM scheduler, registers the five agents,
wires their cron/interval triggers, and exposes a single `status()` snapshot
that the web dashboard renders.

Triggering an agent never runs it inline — it *submits* the agent to the LLM
scheduler, which enforces throttling, resource locking and deadlock prevention.
"""
from __future__ import annotations

import logging
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings
from core import database as db
from core.llm import llm
from orchestrator.resource_monitor import ResourceMonitor
from orchestrator.scheduler import LLMScheduler

log = logging.getLogger("orchestrator")


class Orchestrator:
    def __init__(self) -> None:
        db.init_db()
        self.monitor = ResourceMonitor(interval_s=3)
        self.scheduler = LLMScheduler(self.monitor, workers=2)
        self.cron = BackgroundScheduler(daemon=True)
        self.agents: dict[str, "BaseAgent"] = {}  # noqa: F821 - type hint only
        self.started_at = time.time()

    # ----- registration ---------------------------------------------------- #
    def register(self, agent) -> None:
        self.agents[agent.name] = agent
        log.info("Registered agent: %s (priority=%d)", agent.name, agent.priority)

    def _add_trigger(self, agent, trigger) -> None:
        self.cron.add_job(
            self._dispatch,
            trigger=trigger,
            args=[agent.name],
            id=f"trigger-{agent.name}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    def _wire_triggers(self) -> None:
        def _hm(value: str) -> tuple[int, int]:
            h, m = value.split(":")
            return int(h), int(m)

        if "AI-Times" in self.agents:
            h, m = _hm(settings.ai_times_run_at)
            self._add_trigger(self.agents["AI-Times"], CronTrigger(hour=h, minute=m))
        if "Mailman" in self.agents:
            self._add_trigger(
                self.agents["Mailman"],
                IntervalTrigger(minutes=settings.mailman_interval_minutes),
            )
        if "Wallstreet-Wolf" in self.agents:
            h, m = _hm(settings.wallstreet_run_at)
            self._add_trigger(self.agents["Wallstreet-Wolf"], CronTrigger(hour=h, minute=m))
        if "Calendar-Optimizer" in self.agents:
            h, m = _hm(settings.calendar_run_at)
            self._add_trigger(self.agents["Calendar-Optimizer"], CronTrigger(hour=h, minute=m))

    # ----- dispatch -------------------------------------------------------- #
    def _dispatch(self, agent_name: str) -> None:
        """Hand an agent to the LLM scheduler (called by cron or the dashboard)."""
        agent = self.agents.get(agent_name)
        if not agent:
            log.warning("Unknown agent dispatched: %s", agent_name)
            return
        self.scheduler.submit(
            agent=agent.name,
            fn=agent.run,
            priority=agent.priority,
            resources=agent.resources,
            name=f"{agent.name} run",
        )

    def run_now(self, agent_name: str) -> bool:
        """Manual trigger from the dashboard. Returns True if the agent exists."""
        if agent_name not in self.agents:
            return False
        self._dispatch(agent_name)
        return True

    # ----- lifecycle ------------------------------------------------------- #
    def start(self) -> None:
        self.monitor.start()
        self.scheduler.start()
        self._wire_triggers()
        self.cron.start()
        log.info("Orchestrator online. LLM available: %s", llm.is_available())

    def shutdown(self) -> None:
        self.cron.shutdown(wait=False)
        self.scheduler.stop()
        self.monitor.stop()

    # ----- status (dashboard) --------------------------------------------- #
    def status(self) -> dict:
        snap = self.monitor.latest
        overloaded, reason = self.monitor.is_overloaded()
        sched = self.scheduler.status()
        return {
            "llm": {
                "model": llm.model,
                "base_url": llm.base_url,
                "available": llm.is_available(),
            },
            "overview": {
                "uptime_seconds": round(time.time() - self.started_at),
                "threads": threading.active_count(),
                "agents_managed": len(self.agents),
                "agents_running": len(sched["active"]),
            },
            "resources": {
                **snap.as_dict(),
                "overloaded": overloaded,
                "throttle_reason": reason,
                "limits": {
                    "cpu": settings.cpu_throttle_percent,
                    "ram": settings.ram_throttle_percent,
                    "disk": settings.disk_alert_percent,
                },
            },
            "scheduler": sched,
            "agents": [a.describe() for a in self.agents.values()],
        }
