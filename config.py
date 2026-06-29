"""
Central configuration loaded from environment (.env).

Every tunable lives here so the rest of the codebase never reads os.environ
directly. Import `settings` anywhere you need configuration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _get_list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- Local LLM ---
    ollama_base_url: str = field(default_factory=lambda: _get("OLLAMA_BASE_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: _get("OLLAMA_MODEL", "qwen3:8b"))
    llm_timeout_seconds: int = field(default_factory=lambda: _get_int("LLM_TIMEOUT_SECONDS", 120))

    # --- Orchestrator ---
    cpu_throttle_percent: int = field(default_factory=lambda: _get_int("CPU_THROTTLE_PERCENT", 85))
    ram_throttle_percent: int = field(default_factory=lambda: _get_int("RAM_THROTTLE_PERCENT", 90))
    disk_alert_percent: int = field(default_factory=lambda: _get_int("DISK_ALERT_PERCENT", 90))
    llm_lock_timeout_seconds: int = field(default_factory=lambda: _get_int("LLM_LOCK_TIMEOUT_SECONDS", 180))

    # --- Email ---
    smtp_host: str = field(default_factory=lambda: _get("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = field(default_factory=lambda: _get_int("SMTP_PORT", 587))
    smtp_username: str = field(default_factory=lambda: _get("SMTP_USERNAME"))
    smtp_password: str = field(default_factory=lambda: _get("SMTP_PASSWORD"))
    email_from: str = field(default_factory=lambda: _get("EMAIL_FROM"))
    email_to: str = field(default_factory=lambda: _get("EMAIL_TO"))

    # --- AI-Times ---
    youtube_api_key: str = field(default_factory=lambda: _get("YOUTUBE_API_KEY"))
    ai_times_query: str = field(default_factory=lambda: _get("AI_TIMES_QUERY", "artificial intelligence"))
    ai_times_max_results: int = field(default_factory=lambda: _get_int("AI_TIMES_MAX_RESULTS", 8))

    # --- Google OAuth (Gmail + Calendar) ---
    google_client_secret_file: str = field(default_factory=lambda: _get("GOOGLE_CLIENT_SECRET_FILE", "credentials/google_client_secret.json"))
    google_token_file: str = field(default_factory=lambda: _get("GOOGLE_TOKEN_FILE", "credentials/google_token.json"))

    # --- Wallstreet Wolf ---
    stock_tickers: list[str] = field(default_factory=lambda: _get_list(
        "STOCK_TICKERS",
        "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,AMD,INTC,NFLX,ORCL,CRM,ADBE,CSCO,QCOM,IBM,AVGO,TXN,PYPL,UBER,JPM,V",
    ))

    # --- Schedules ---
    ai_times_run_at: str = field(default_factory=lambda: _get("AI_TIMES_RUN_AT", "08:00"))
    mailman_interval_minutes: int = field(default_factory=lambda: _get_int("MAILMAN_INTERVAL_MINUTES", 15))
    wallstreet_run_at: str = field(default_factory=lambda: _get("WALLSTREET_RUN_AT", "17:30"))
    calendar_run_at: str = field(default_factory=lambda: _get("CALENDAR_RUN_AT", "07:00"))

    # --- Web ---
    web_host: str = field(default_factory=lambda: _get("WEB_HOST", "127.0.0.1"))
    web_port: int = field(default_factory=lambda: _get_int("WEB_PORT", 8000))

    # --- Paths ---
    base_dir: Path = BASE_DIR
    db_path: Path = BASE_DIR / "data" / "platform.sqlite3"


settings = Settings()

# Ensure runtime directories exist.
(settings.base_dir / "data").mkdir(exist_ok=True)
(settings.base_dir / "credentials").mkdir(exist_ok=True)
