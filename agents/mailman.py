"""
Mailman agent.

Polls the Gmail inbox for unread messages, classifies each one with the local
LLM (category + priority), then applies a Gmail label, stars high-priority mail,
and emails an alert digest for anything urgent.

Without Google credentials it classifies a small set of sample emails so the
LLM-classification pipeline is still demonstrable.
"""
from __future__ import annotations

import base64
import html
import logging

from agents.base_agent import BaseAgent
from core import database as db
from core.emailer import send_html
from core.llm import llm

log = logging.getLogger("Mailman")

CATEGORIES = ["urgent", "work", "personal", "finance", "newsletter", "promotion", "spam"]


class MailmanAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Mailman",
            description="Classifies unread Gmail with the local LLM; labels, stars, alerts.",
            priority=3,                       # mail is time-sensitive -> high priority
            resources=["network", "gmail"],
        )

    # ------------------------------------------------------------------ #
    def execute(self) -> str:
        service = self._gmail()
        if service is None:
            return self._demo()

        messages = self._unread(service)
        if not messages:
            return "Inbox clean — no unread mail."

        urgent: list[dict] = []
        for meta in messages:
            subject, sender, snippet = self._headers(service, meta["id"])
            category = self._classify(subject, sender, snippet)
            self._apply_label(service, meta["id"], category)
            if category == "urgent":
                self._star(service, meta["id"])
                urgent.append({"subject": subject, "sender": sender})
            db.save_output(self.name, subject, f"{sender} → {category}", meta=category)

        if urgent:
            send_html("⚠️ Mailman — Urgent mail", self._alert(urgent))
        return f"Classified {len(messages)} emails; {len(urgent)} urgent."

    # ------------------------------------------------------------------ #
    def _classify(self, subject: str, sender: str, snippet: str) -> str:
        if not llm.is_available():
            return "newsletter"
        prompt = (
            f"From: {sender}\nSubject: {subject}\nPreview: {snippet[:300]}\n\n"
            "Classify this email."
        )
        try:
            return llm.classify(prompt, CATEGORIES)
        except Exception:  # noqa: BLE001
            return "work"

    # ------------------------------------------------------------------ #
    # Gmail plumbing
    # ------------------------------------------------------------------ #
    def _gmail(self):
        try:
            from agents.google_auth import build_service

            return build_service("gmail", "v1")
        except Exception as exc:  # noqa: BLE001
            log.warning("Gmail unavailable (%s); running demo mode.", exc)
            return None

    @staticmethod
    def _unread(service) -> list[dict]:
        resp = service.users().messages().list(
            userId="me", q="is:unread", maxResults=20
        ).execute()
        return resp.get("messages", [])

    @staticmethod
    def _headers(service, msg_id: str) -> tuple[str, str, str]:
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="metadata",
            metadataHeaders=["Subject", "From"],
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        return headers.get("Subject", "(no subject)"), headers.get("From", "(unknown)"), msg.get("snippet", "")

    def _apply_label(self, service, msg_id: str, category: str) -> None:
        label_id = self._ensure_label(service, f"AI/{category}")
        service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": [label_id]}
        ).execute()

    @staticmethod
    def _star(service, msg_id: str) -> None:
        service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": ["STARRED"]}
        ).execute()

    _label_cache: dict[str, str] = {}

    def _ensure_label(self, service, name: str) -> str:
        if name in self._label_cache:
            return self._label_cache[name]
        existing = service.users().labels().list(userId="me").execute().get("labels", [])
        for lbl in existing:
            if lbl["name"] == name:
                self._label_cache[name] = lbl["id"]
                return lbl["id"]
        created = service.users().labels().create(
            userId="me",
            body={"name": name, "labelListVisibility": "labelShow",
                  "messageListVisibility": "show"},
        ).execute()
        self._label_cache[name] = created["id"]
        return created["id"]

    # ------------------------------------------------------------------ #
    @staticmethod
    def _alert(urgent: list[dict]) -> str:
        rows = "".join(
            f"<li><b>{html.escape(u['subject'])}</b> — {html.escape(u['sender'])}</li>"
            for u in urgent
        )
        return f"""
        <html><body style="font-family:Arial,sans-serif;padding:20px;">
          <h2 style="color:#b91c1c;">⚠️ Urgent emails need your attention</h2>
          <ul>{rows}</ul>
        </body></html>"""

    # ------------------------------------------------------------------ #
    def _demo(self) -> str:
        samples = [
            ("Server is down in production!", "ops@company.com", "PagerDuty alert: API 500s spiking."),
            ("Your invoice for June", "billing@vendor.com", "Amount due $240, pay by July 3."),
            ("Weekend hiking trip?", "alex@friends.com", "Want to join us Saturday morning?"),
            ("50% OFF everything today", "deals@shop.com", "Limited time mega sale, shop now!"),
        ]
        urgent = 0
        for subject, sender, snippet in samples:
            category = self._classify(subject, sender, snippet)
            if category == "urgent":
                urgent += 1
            db.save_output(self.name, subject, f"{sender} → {category}", meta=category)
        return f"[demo] Classified {len(samples)} sample emails; {urgent} urgent."
