"""The five specialized agents managed by the orchestrator."""
from agents.ai_times import AITimesAgent
from agents.calendar_optimizer import CalendarOptimizerAgent
from agents.mailman import MailmanAgent
from agents.wallstreet_wolf import WallstreetWolfAgent

__all__ = [
    "AITimesAgent",
    "MailmanAgent",
    "WallstreetWolfAgent",
    "CalendarOptimizerAgent",
]
