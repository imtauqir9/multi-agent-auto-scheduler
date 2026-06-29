"""
Entry point for the Multi-Agent Auto-Scheduling Platform.

Usage
-----
    python run.py                 # start the dashboard + orchestrator (default)
    python run.py --agent Mailman # run a single agent once, then exit (debug)
    python run.py --check         # environment self-check (LLM, DB, config)

Open the dashboard at http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import sys


def _check() -> None:
    from core import database as db
    from core.llm import llm
    from config import settings

    db.init_db()
    print("Configuration")
    print(f"  LLM model        : {settings.ollama_model}")
    print(f"  Ollama URL       : {settings.ollama_base_url}")
    print(f"  LLM reachable    : {llm.is_available()}")
    print(f"  Tickers tracked  : {len(settings.stock_tickers)}")
    print(f"  Database         : {settings.db_path}")
    print(f"  Dashboard        : http://{settings.web_host}:{settings.web_port}")
    if not llm.is_available():
        print("\n  [!] Ollama not reachable. Run:  ollama serve  &&  ollama pull", settings.ollama_model)


def _run_single(name: str) -> None:
    from core import database as db
    from agents import (
        AITimesAgent,
        CalendarOptimizerAgent,
        MailmanAgent,
        WallstreetWolfAgent,
    )

    db.init_db()
    registry = {
        "AI-Times": AITimesAgent,
        "Mailman": MailmanAgent,
        "Wallstreet-Wolf": WallstreetWolfAgent,
        "Calendar-Optimizer": CalendarOptimizerAgent,
    }
    cls = registry.get(name)
    if not cls:
        print(f"Unknown agent '{name}'. Choose from: {', '.join(registry)}")
        sys.exit(1)
    print(f"Running {name} once…")
    print("Result:", cls().run())


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Agent Auto-Scheduling Platform")
    parser.add_argument("--agent", help="Run a single agent once and exit")
    parser.add_argument("--check", action="store_true", help="Environment self-check")
    args = parser.parse_args()

    if args.check:
        _check()
    elif args.agent:
        _run_single(args.agent)
    else:
        from web.server import main as serve

        serve()


if __name__ == "__main__":
    main()
