"""
Shared Google OAuth helper for the Gmail (Mailman) and Calendar (Calendar
Optimizer) agents. Uses the standard installed-app OAuth flow; the token is
cached to disk so authorization only happens once.
"""
from __future__ import annotations

import logging
from pathlib import Path

from config import settings

log = logging.getLogger("google_auth")

# Combined scopes for both Google agents.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def get_credentials():
    """
    Return valid Google OAuth credentials, refreshing or running the consent
    flow as needed. Raises FileNotFoundError if the client-secret file is
    missing so the agent can degrade gracefully.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = Path(settings.google_token_file)
    secret_path = Path(settings.google_client_secret_file)
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not secret_path.exists():
            raise FileNotFoundError(
                f"Google client secret not found at {secret_path}. "
                "Download OAuth credentials from Google Cloud Console."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
        creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_service(api: str, version: str):
    from googleapiclient.discovery import build

    return build(api, version, credentials=get_credentials(), cache_discovery=False)
