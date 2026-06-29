"""
FastAPI application: serves the dashboard and the JSON API the front-end polls.

The orchestrator instance is created here and shared with every request. Cron
triggers and the resource monitor run on background threads, so the API is just
a thin read/command layer over the live orchestrator.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agents import (
    AITimesAgent,
    CalendarOptimizerAgent,
    MailmanAgent,
    WallstreetWolfAgent,
)
from config import settings
from core import database as db
from orchestrator.orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)-18s %(message)s",
    datefmt="%H:%M:%S",
)

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Multi-Agent Auto-Scheduling Platform")
orch = Orchestrator()


@app.on_event("startup")
def _startup() -> None:
    orch.register(AITimesAgent())
    orch.register(MailmanAgent())
    orch.register(WallstreetWolfAgent())
    orch.register(CalendarOptimizerAgent())
    orch.start()


@app.on_event("shutdown")
def _shutdown() -> None:
    orch.shutdown()


# ----------------------------- API ------------------------------------- #
@app.get("/api/status")
def api_status() -> JSONResponse:
    return JSONResponse(orch.status())


@app.get("/api/runs")
def api_runs() -> JSONResponse:
    return JSONResponse(db.recent_runs())


@app.get("/api/schedule")
def api_schedule() -> JSONResponse:
    return JSONResponse(db.recent_schedule())


@app.get("/api/outputs")
def api_outputs() -> JSONResponse:
    return JSONResponse(db.recent_outputs())


@app.get("/api/resources")
def api_resources() -> JSONResponse:
    return JSONResponse(db.recent_resources())


@app.post("/api/run/{agent_name}")
def api_run(agent_name: str) -> JSONResponse:
    if not orch.run_now(agent_name):
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")
    return JSONResponse({"queued": agent_name})


# --------------------------- static UI --------------------------------- #
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=settings.web_host, port=settings.web_port)


if __name__ == "__main__":
    main()
