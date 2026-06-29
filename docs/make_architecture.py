"""
Generates the architecture diagram (architecture.png) for the platform.
Run:  python docs/make_architecture.py
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.pyplot as plt

BG = "#0b1120"
PANEL = "#1b263f"
ACCENT = "#3b82f6"
GREEN = "#22c55e"
AMBER = "#f59e0b"
RED = "#ef4444"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"

fig, ax = plt.subplots(figsize=(14, 9))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 14)
ax.set_ylim(0, 9)
ax.axis("off")


def box(x, y, w, h, title, subtitle="", color=PANEL, edge=ACCENT, tcolor=TEXT, fs=11):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.6, edgecolor=edge, facecolor=color, zorder=2,
        )
    )
    ax.text(x + w / 2, y + h / 2 + (0.14 if subtitle else 0), title,
            ha="center", va="center", color=tcolor, fontsize=fs, fontweight="bold", zorder=3)
    if subtitle:
        ax.text(x + w / 2, y + h / 2 - 0.22, subtitle, ha="center", va="center",
                color=MUTED, fontsize=8.5, zorder=3)


def arrow(x1, y1, x2, y2, color=MUTED, style="-|>", lw=1.4):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=14, color=color, lw=lw, zorder=1))


# Title
ax.text(7, 8.6, "Multi-Agent Personal Auto-Scheduling Platform",
        ha="center", color=TEXT, fontsize=18, fontweight="bold")
ax.text(7, 8.2, "100% local inference · Qwen3 via Ollama · Python 3.12 · SQLite · HTML/JS dashboard",
        ha="center", color=MUTED, fontsize=10)

# Dashboard (top)
box(5.0, 7.1, 4.0, 0.8, "Web Dashboard (HTML/JS)",
    "FastAPI · /api/status · polls every 3s", color="#11213f", edge=GREEN)

# Orchestrator (center)
box(4.3, 4.9, 5.4, 1.6, "MAIN ORCHESTRATOR", color="#10204a", edge=ACCENT, fs=13)
box(4.55, 5.6, 1.55, 0.55, "Resource Monitor", "psutil CPU/RAM/disk", color=PANEL, edge=AMBER, fs=8.5)
box(6.25, 5.6, 1.55, 0.55, "LLM Scheduler", "priority queue · throttle", color=PANEL, edge=AMBER, fs=8.5)
box(7.95, 5.6, 1.5, 0.55, "Deadlock Prev.", "wait-die + ordering", color=PANEL, edge=RED, fs=8.5)
box(4.55, 5.0, 4.9, 0.45, "Agent Manager + APScheduler (cron / interval triggers)",
    color=PANEL, edge=ACCENT, fs=8.5)

arrow(7.0, 7.1, 7.0, 6.55, color=GREEN)
arrow(7.0, 6.55, 7.0, 7.05, color=GREEN)

# Local LLM (right)
box(11.0, 5.2, 2.6, 1.0, "Local LLM", "Ollama / LM Studio\nQwen3 (single shared GPU)",
    color="#231034", edge="#a855f7", fs=11)
arrow(9.7, 5.7, 11.0, 5.7, color="#a855f7", lw=2.0)
ax.text(10.35, 5.95, "1 lock", ha="center", color="#a855f7", fontsize=8)

# SQLite (left)
box(0.3, 5.2, 2.6, 1.0, "SQLite", "agent_runs · resource_stats\nscheduler_log · agent_outputs",
    color="#0f2a22", edge=GREEN, fs=11)
arrow(4.3, 5.7, 2.9, 5.7, color=GREEN)

# Agents (bottom row)
agents = [
    ("1 · AI-Times", "YouTube API →\nLLM blurbs → email", "#11213f"),
    ("2 · Mailman", "Gmail classify\nlabel · star · alert", "#11213f"),
    ("3 · Wallstreet Wolf", "yfinance 20+ stocks\nLLM commentary", "#11213f"),
    ("4 · Calendar Optimizer", "Google Calendar\nconflict-free day plan", "#11213f"),
]
xs = [0.4, 3.7, 7.0, 10.3]
clamp = lambda v: max(4.5, min(9.5, v))
for (title, sub, c), x in zip(agents, xs):
    box(x, 2.4, 3.0, 1.2, title, sub, color=c, edge=ACCENT, fs=10.5)
    arrow(x + 1.5, 3.6, clamp(x + 1.5), 4.9, color=MUTED)

# external APIs row
ext = ["YouTube Data API", "Gmail API", "Yahoo Finance", "Google Calendar API"]
for label, x in zip(ext, xs):
    box(x + 0.4, 0.9, 2.2, 0.55, label, color="#1a1a2e", edge=MUTED, tcolor=MUTED, fs=8.5)
    arrow(x + 1.5, 1.45, x + 1.5, 2.4, color=MUTED, style="<|-|>")

# 5th agent note
ax.text(7, 0.35, "Agent 4 (Calendar Optimizer) = the custom 'Your Choice' agent: external API + local LLM solving a real scheduling problem.",
        ha="center", color=MUTED, fontsize=9, style="italic")

# Legend
legend = [
    mpatches.Patch(color=ACCENT, label="control / data flow"),
    mpatches.Patch(color="#a855f7", label="serialized LLM access"),
    mpatches.Patch(color=RED, label="deadlock prevention"),
    mpatches.Patch(color=GREEN, label="persistence / UI"),
]
ax.legend(handles=legend, loc="upper left", facecolor=PANEL, edgecolor=PANEL,
          labelcolor=TEXT, fontsize=8.5, framealpha=0.9)

plt.tight_layout()
out = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
plt.savefig(f"{out}/architecture.png", dpi=160, facecolor=BG, bbox_inches="tight")
print("wrote architecture.png")
