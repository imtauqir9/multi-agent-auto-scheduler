"""
Wallstreet Wolf agent.

Pulls quotes for 20+ tickers from Yahoo Finance (yfinance), asks the local LLM
for a short market-commentary paragraph over the day's movers, and emails a
daily HTML portfolio report.
"""
from __future__ import annotations

import html
import logging

from agents.base_agent import BaseAgent
from config import settings
from core import database as db
from core.emailer import send_html
from core.llm import llm

log = logging.getLogger("Wallstreet-Wolf")


class WallstreetWolfAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(
            name="Wallstreet-Wolf",
            description="Tracks 20+ stocks via Yahoo Finance; LLM commentary; daily email.",
            priority=5,
            resources=["network", "yfinance"],
        )

    # ------------------------------------------------------------------ #
    def execute(self) -> str:
        quotes = self._fetch_quotes()
        if not quotes:
            return "No quotes retrieved."

        commentary = self._commentary(quotes)
        html_body = self._render(quotes, commentary)
        sent = send_html("📈 Wallstreet Wolf — Daily Market Report", html_body)

        # Surface the FULL watchlist on the dashboard (losers first so the
        # biggest gainers sort to the top), then the LLM commentary on top.
        for q in sorted(quotes, key=lambda x: x["change_pct"]):
            tag = "gainer" if q["change_pct"] >= 0 else "loser"
            db.save_output(
                self.name, q["ticker"],
                f"${q['price']:.2f}  ({q['change_pct']:+.2f}%)", meta=tag,
            )
        db.save_output(self.name, "Market commentary", commentary[:300], meta="LLM")

        movers = sorted(quotes, key=lambda q: abs(q["change_pct"]), reverse=True)
        return (
            f"Report on {len(quotes)} tickers "
            f"({'emailed' if sent else 'saved to outbox'}); "
            f"top mover {movers[0]['ticker']} {movers[0]['change_pct']:+.2f}%."
        )

    # ------------------------------------------------------------------ #
    def _fetch_quotes(self) -> list[dict]:
        try:
            import yfinance as yf
        except Exception as exc:  # noqa: BLE001
            log.error("yfinance import failed: %s", exc)
            return []

        quotes: list[dict] = []
        tickers = settings.stock_tickers
        try:
            data = yf.download(
                tickers=" ".join(tickers),
                period="2d",
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Bulk download failed: %s", exc)
            return []

        for t in tickers:
            try:
                df = data[t] if len(tickers) > 1 else data
                closes = df["Close"].dropna()
                if len(closes) < 1:
                    continue
                price = float(closes.iloc[-1])
                prev = float(closes.iloc[-2]) if len(closes) >= 2 else price
                change_pct = ((price - prev) / prev * 100) if prev else 0.0
                quotes.append({"ticker": t, "price": round(price, 2),
                               "change_pct": round(change_pct, 2)})
            except Exception:  # noqa: BLE001
                continue
        return quotes

    # ------------------------------------------------------------------ #
    def _commentary(self, quotes: list[dict]) -> str:
        if not llm.is_available():
            return "Local LLM offline — commentary unavailable."
        table = "\n".join(f"{q['ticker']}: ${q['price']} ({q['change_pct']:+.2f}%)" for q in quotes)
        prompt = (
            f"Here are today's closing quotes:\n{table}\n\n"
            "Write a 3-4 sentence market commentary: note the biggest gainers and "
            "losers and any sector pattern. Be factual, no investment advice."
        )
        try:
            return llm.generate(prompt, system="You are a neutral market analyst.", temperature=0.4)
        except Exception:  # noqa: BLE001
            return "(commentary generation failed)"

    # ------------------------------------------------------------------ #
    @staticmethod
    def _render(quotes: list[dict], commentary: str) -> str:
        rows = []
        for q in sorted(quotes, key=lambda x: x["change_pct"], reverse=True):
            color = "#16a34a" if q["change_pct"] >= 0 else "#dc2626"
            rows.append(
                f"<tr>"
                f"<td style='padding:6px 12px;font-weight:600;'>{html.escape(q['ticker'])}</td>"
                f"<td style='padding:6px 12px;text-align:right;'>${q['price']:.2f}</td>"
                f"<td style='padding:6px 12px;text-align:right;color:{color};'>{q['change_pct']:+.2f}%</td>"
                f"</tr>"
            )
        return f"""
        <html><body style="font-family:Arial,sans-serif;background:#f8fafc;padding:24px;">
          <h1 style="color:#0f172a;">📈 Wallstreet Wolf</h1>
          <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin-bottom:16px;">
            <h3 style="margin-top:0;color:#334155;">Market Commentary</h3>
            <p style="color:#475569;line-height:1.5;">{html.escape(commentary)}</p>
          </div>
          <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:10px;">
            <tr style="background:#f1f5f9;text-align:left;">
              <th style="padding:8px 12px;">Ticker</th>
              <th style="padding:8px 12px;text-align:right;">Price</th>
              <th style="padding:8px 12px;text-align:right;">Change</th>
            </tr>
            {''.join(rows)}
          </table>
          <p style="color:#94a3b8;font-size:12px;margin-top:16px;">
            Local inference via Qwen3/Ollama · Not investment advice.
          </p>
        </body></html>"""
