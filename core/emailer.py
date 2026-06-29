"""
HTML e-mail sender over SMTP (used by AI-Times, Wallstreet Wolf, Mailman alerts).

If SMTP credentials are not configured the email is written to
data/outbox/ as an .html file instead of being sent, so the platform still
runs end-to-end for a demo without real credentials.
"""
from __future__ import annotations

import logging
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import settings

log = logging.getLogger("emailer")
OUTBOX = settings.base_dir / "data" / "outbox"
OUTBOX.mkdir(parents=True, exist_ok=True)


def send_html(subject: str, html_body: str, to: str | None = None) -> bool:
    """
    Send an HTML email. Returns True if dispatched via SMTP, False if it was
    saved to the local outbox (no credentials / SMTP failure).
    """
    recipient = to or settings.email_to
    configured = bool(settings.smtp_username and settings.smtp_password and recipient)

    if not configured:
        return _save_to_outbox(subject, html_body, reason="SMTP not configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from or settings.smtp_username
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        log.info("Email sent: %s", subject)
        return True
    except Exception as exc:  # pragma: no cover - network failure path
        log.warning("SMTP send failed (%s); saving to outbox", exc)
        return _save_to_outbox(subject, html_body, reason=str(exc))


def _save_to_outbox(subject: str, html_body: str, reason: str) -> bool:
    safe = "".join(c if c.isalnum() else "_" for c in subject)[:60]
    path: Path = OUTBOX / f"{int(time.time())}_{safe}.html"
    path.write_text(html_body, encoding="utf-8")
    log.info("Email saved to outbox (%s): %s", reason, path.name)
    return False
