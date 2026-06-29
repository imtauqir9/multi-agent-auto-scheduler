"""
AI-Times agent.

Fetches the latest AI-related YouTube videos (YouTube Data API v3), asks the
local LLM to write a one-line "why it matters" blurb per video, and emails a
clean HTML digest. Without a YouTube API key it falls back to a small sample
feed so the platform still demonstrates end-to-end.
"""
from __future__ import annotations

import html
import logging

from agents.base_agent import BaseAgent
from config import settings
from core import database as db
from core.emailer import send_html
from core.llm import llm

log = logging.getLogger("AI-Times")


class AITimesAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="AI-Times",
            description="Daily HTML digest of the latest AI YouTube videos.",
            priority=6,
            resources=["network", "youtube"],
        )

    # ------------------------------------------------------------------ #
    def execute(self) -> str:
        videos = self._fetch_videos()
        if not videos:
            return "No videos found."

        for v in videos:
            v["blurb"] = self._blurb(v)

        html_body = self._render(videos)
        sent = send_html("🤖 AI-Times — Today's AI Videos", html_body)
        db.save_output(
            self.name,
            "AI-Times digest",
            f"{len(videos)} videos",
            meta="sent" if sent else "outbox",
        )
        return f"Digest with {len(videos)} videos ({'emailed' if sent else 'saved to outbox'})."

    # ------------------------------------------------------------------ #
    def _fetch_videos(self) -> list[dict]:
        if not settings.youtube_api_key:
            log.warning("No YOUTUBE_API_KEY; using sample feed.")
            return _SAMPLE_FEED[: settings.ai_times_max_results]
        try:
            from googleapiclient.discovery import build

            yt = build("youtube", "v3", developerKey=settings.youtube_api_key, cache_discovery=False)
            resp = (
                yt.search()
                .list(
                    q=settings.ai_times_query,
                    part="snippet",
                    type="video",
                    order="date",
                    maxResults=settings.ai_times_max_results,
                )
                .execute()
            )
            videos = []
            for item in resp.get("items", []):
                vid = item["id"]["videoId"]
                sn = item["snippet"]
                videos.append(
                    {
                        "title": sn["title"],
                        "channel": sn["channelTitle"],
                        "published": sn["publishedAt"][:10],
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "description": sn.get("description", ""),
                    }
                )
            return videos
        except Exception as exc:  # noqa: BLE001
            log.warning("YouTube fetch failed (%s); using sample feed.", exc)
            return _SAMPLE_FEED[: settings.ai_times_max_results]

    # ------------------------------------------------------------------ #
    def _blurb(self, video: dict) -> str:
        if not llm.is_available():
            return "Local LLM offline — blurb unavailable."
        prompt = (
            f"Title: {video['title']}\n"
            f"Channel: {video['channel']}\n"
            f"Description: {video['description'][:400]}\n\n"
            "In ONE sentence (max 25 words), say why an AI practitioner should care."
        )
        try:
            return llm.generate(prompt, system="You are a concise tech editor.", temperature=0.5)
        except Exception:  # noqa: BLE001
            return "(blurb generation failed)"

    # ------------------------------------------------------------------ #
    @staticmethod
    def _render(videos: list[dict]) -> str:
        cards = []
        for v in videos:
            cards.append(
                f"""
                <div style="border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin:12px 0;">
                  <a href="{html.escape(v['url'])}" style="font-size:16px;font-weight:700;color:#1d4ed8;text-decoration:none;">
                    {html.escape(v['title'])}
                  </a>
                  <div style="color:#64748b;font-size:13px;margin:4px 0;">
                    {html.escape(v['channel'])} · {html.escape(v['published'])}
                  </div>
                  <div style="color:#334155;font-size:14px;">{html.escape(v['blurb'])}</div>
                </div>"""
            )
        return f"""
        <html><body style="font-family:Arial,Helvetica,sans-serif;background:#f8fafc;padding:24px;">
          <h1 style="color:#0f172a;">🤖 AI-Times</h1>
          <p style="color:#475569;">Your daily roundup of the latest AI videos.</p>
          {''.join(cards)}
          <p style="color:#94a3b8;font-size:12px;margin-top:24px;">
            Generated locally by the Multi-Agent Auto-Scheduling Platform · Qwen3 via Ollama
          </p>
        </body></html>"""


_SAMPLE_FEED = [
    {
        "title": "What Are AI Agents? A Practical Introduction",
        "channel": "Local AI Lab",
        "published": "2026-06-25",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "description": "An overview of agentic architectures, orchestration patterns and tool use.",
    },
    {
        "title": "Running Qwen3 Locally with Ollama",
        "channel": "Edge LLM",
        "published": "2026-06-24",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "description": "Step-by-step guide to serving Qwen3 on consumer hardware.",
    },
    {
        "title": "Deadlock Prevention in Multi-Agent Systems",
        "channel": "Systems Deep Dive",
        "published": "2026-06-23",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "description": "Wait-die, wound-wait and resource ordering explained with examples.",
    },
]
