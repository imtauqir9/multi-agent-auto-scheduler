"""
Calendar Optimizer agent  (the custom "Your Choice" agent).

Real problem: people start the day with a messy calendar — overlapping events,
no focus blocks, deadlines scattered around. This agent reads today's Google
Calendar events, detects conflicts and gaps, and asks the local LLM to propose
an optimized, conflict-free day plan (focus blocks, buffer time, deadline-aware
ordering). It emails the plan and surfaces it on the dashboard.

External API: Google Calendar.  Local LLM: Qwen3 via Ollama.

Without Google credentials it optimizes a sample schedule so the
plan-generation pipeline is still demonstrable.
"""
from __future__ import annotations

import datetime as dt
import html
import logging

from agents.base_agent import BaseAgent
from core import database as db
from core.emailer import send_html
from core.llm import llm

log = logging.getLogger("Calendar-Optimizer")


class CalendarOptimizerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Calendar-Optimizer",
            description="Reads today's calendar, detects conflicts/gaps, LLM proposes an optimized day plan.",
            priority=4,
            resources=["network", "calendar"],
        )

    # ------------------------------------------------------------------ #
    def execute(self) -> str:
        events = self._todays_events()
        if not events:
            return "No events today — nothing to optimize."

        conflicts = self._detect_conflicts(events)
        plan = self._optimize(events, conflicts)

        html_body = self._render(events, conflicts, plan)
        sent = send_html("🗓️ Calendar Optimizer — Your Optimized Day", html_body)

        # Surface today's schedule, the conflicts found, and the optimized plan
        # (plan saved last so it sorts to the top).
        for e in events:
            db.save_output(self.name, e["summary"], f"{e['start']}–{e['end']}", meta="event")
        for a, b in conflicts:
            db.save_output(self.name, "Conflict", f"{a} ↔ {b}", meta="conflict")
        db.save_output(self.name, "Optimized day plan", plan[:400], meta="plan")
        return (
            f"Optimized {len(events)} events, {len(conflicts)} conflict(s) "
            f"({'emailed' if sent else 'saved to outbox'})."
        )

    # ------------------------------------------------------------------ #
    def _todays_events(self) -> list[dict]:
        service = self._calendar()
        if service is None:
            return _SAMPLE_EVENTS

        now = dt.datetime.utcnow()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "Z"
        end = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + "Z"
        try:
            resp = service.events().list(
                calendarId="primary", timeMin=start, timeMax=end,
                singleEvents=True, orderBy="startTime",
            ).execute()
        except Exception as exc:  # noqa: BLE001
            log.warning("Calendar fetch failed (%s); using sample events.", exc)
            return _SAMPLE_EVENTS

        events = []
        for item in resp.get("items", []):
            s = item["start"].get("dateTime", item["start"].get("date"))
            e = item["end"].get("dateTime", item["end"].get("date"))
            events.append({"summary": item.get("summary", "(no title)"),
                           "start": s[11:16] if len(s) > 10 else "00:00",
                           "end": e[11:16] if len(e) > 10 else "23:59"})
        return events or _SAMPLE_EVENTS

    def _calendar(self):
        try:
            from agents.google_auth import build_service

            return build_service("calendar", "v3")
        except Exception as exc:  # noqa: BLE001
            log.warning("Calendar unavailable (%s); demo mode.", exc)
            return None

    # ------------------------------------------------------------------ #
    @staticmethod
    def _detect_conflicts(events: list[dict]) -> list[tuple[str, str]]:
        def to_min(t: str) -> int:
            h, m = t.split(":")
            return int(h) * 60 + int(m)

        ordered = sorted(events, key=lambda e: to_min(e["start"]))
        conflicts = []
        for i in range(len(ordered) - 1):
            if to_min(ordered[i]["end"]) > to_min(ordered[i + 1]["start"]):
                conflicts.append((ordered[i]["summary"], ordered[i + 1]["summary"]))
        return conflicts

    # ------------------------------------------------------------------ #
    def _optimize(self, events: list[dict], conflicts: list[tuple[str, str]]) -> str:
        if not llm.is_available():
            return "Local LLM offline — optimized plan unavailable."
        schedule = "\n".join(f"{e['start']}-{e['end']}  {e['summary']}" for e in events)
        conflict_txt = (
            "; ".join(f"{a} overlaps {b}" for a, b in conflicts) if conflicts else "none"
        )
        prompt = (
            f"Today's calendar:\n{schedule}\n\n"
            f"Detected conflicts: {conflict_txt}\n\n"
            "Produce an optimized day plan that: resolves conflicts, inserts a 10-minute "
            "buffer between meetings, protects at least one 90-minute deep-focus block, and "
            "lists items in time order. Return a short bulleted plan with times."
        )
        try:
            return llm.generate(prompt, system="You are an expert executive assistant.", temperature=0.3)
        except Exception:  # noqa: BLE001
            return "(plan generation failed)"

    # ------------------------------------------------------------------ #
    @staticmethod
    def _render(events: list[dict], conflicts: list[tuple[str, str]], plan: str) -> str:
        ev_rows = "".join(
            f"<li>{html.escape(e['start'])}–{html.escape(e['end'])} · {html.escape(e['summary'])}</li>"
            for e in events
        )
        conflict_block = (
            "".join(f"<li style='color:#dc2626;'>{html.escape(a)} ↔ {html.escape(b)}</li>"
                    for a, b in conflicts)
            if conflicts else "<li style='color:#16a34a;'>No conflicts 🎉</li>"
        )
        plan_html = html.escape(plan).replace("\n", "<br>")
        return f"""
        <html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:24px;">
          <h1 style="color:#0f172a;">🗓️ Calendar Optimizer</h1>
          <h3 style="color:#334155;">Today's events</h3>
          <ul style="color:#475569;">{ev_rows}</ul>
          <h3 style="color:#334155;">Conflicts</h3>
          <ul>{conflict_block}</ul>
          <h3 style="color:#334155;">Optimized plan</h3>
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;color:#334155;line-height:1.6;">
            {plan_html}
          </div>
          <p style="color:#94a3b8;font-size:12px;margin-top:16px;">Generated locally by Qwen3/Ollama.</p>
        </body></html>"""


_SAMPLE_EVENTS = [
    {"summary": "Standup", "start": "09:00", "end": "09:30"},
    {"summary": "Design review", "start": "09:15", "end": "10:15"},   # overlaps standup
    {"summary": "1:1 with manager", "start": "11:00", "end": "11:30"},
    {"summary": "Lunch", "start": "12:30", "end": "13:30"},
    {"summary": "Project deadline: submit report", "start": "14:00", "end": "14:15"},
    {"summary": "Client call", "start": "14:00", "end": "15:00"},      # overlaps deadline
    {"summary": "Gym", "start": "18:00", "end": "19:00"},
]
