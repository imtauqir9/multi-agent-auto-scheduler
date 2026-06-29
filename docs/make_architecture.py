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
PURPLE = "#a855f7"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"

fig, ax = plt.subplots(figsize=(15, 10))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 15)
ax.set_ylim(0, 10)
ax.axis("off")


def rrect(x, y, w, h, color, edge, lw=1.6):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.02,rounding_size=0.10",
            linewidth=lw, edgecolor=edge, facecolor=color, zorder=2,
        )
    )


def box(x, y, w, h, title, subtitle="", color=PANEL, edge=ACCENT, tcolor=TEXT, fs=11):
    """A box with its title vertically centred (used for leaf nodes)."""
    rrect(x, y, w, h, color, edge)
    ty = y + h / 2 + (0.12 if subtitle else 0)
    ax.text(x + w / 2, ty, title, ha="center", va="center",
            color=tcolor, fontsize=fs, fontweight="bold", zorder=3)
    if subtitle:
        ax.text(x + w / 2, y + h / 2 - 0.20, subtitle, ha="center", va="center",
                color=MUTED, fontsize=8.5, zorder=3)


def arrow(x1, y1, x2, y2, color=MUTED, style="-|>", lw=1.4):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=14, color=color, lw=lw, zorder=1))


# ---------------- Title ----------------
ax.text(7.5, 9.55, "Multi-Agent Personal Auto-Scheduling Platform",
        ha="center", color=TEXT, fontsize=19, fontweight="bold")
ax.text(7.5, 9.15, "100% local inference · Qwen3 via Ollama · Python 3.12 · SQLite · HTML/JS dashboard",
        ha="center", color=MUTED, fontsize=10.5)

# ---------------- Dashboard (top) ----------------
box(5.3, 8.05, 4.4, 0.75, "Web Dashboard (HTML / JS)",
    "FastAPI · /api/status · polls every 3s", color="#11213f", edge=GREEN)

# ---------------- Orchestrator (center) ----------------
OX0, OY0, OW, OH = 4.0, 5.15, 7.0, 2.2
rrect(OX0, OY0, OW, OH, "#10204a", ACCENT, lw=2.0)
ax.text(OX0 + OW / 2, OY0 + OH - 0.26, "MAIN ORCHESTRATOR",
        ha="center", va="center", color=TEXT, fontsize=14, fontweight="bold", zorder=3)

# three engine sub-boxes (clear of the title)
box(4.30, 6.05, 2.05, 0.66, "Resource Monitor", "psutil CPU/RAM/disk",
    color=PANEL, edge=AMBER, fs=9.5)
box(6.48, 6.05, 2.05, 0.66, "LLM Scheduler", "priority queue · throttle",
    color=PANEL, edge=AMBER, fs=9.5)
box(8.66, 6.05, 1.94, 0.66, "Deadlock Prev.", "wait-die + ordering",
    color=PANEL, edge=RED, fs=9.5)
# agent manager bar
box(4.30, 5.35, 6.30, 0.55, "Agent Manager + APScheduler  (cron / interval triggers)",
    color=PANEL, edge=ACCENT, fs=9.5)

# dashboard <-> orchestrator
arrow(7.5, 8.05, 7.5, 7.35, color=GREEN)
arrow(7.5, 7.35, 7.5, 8.05, color=GREEN)

# ---------------- Local LLM (right) ----------------
box(12.1, 6.0, 2.6, 1.05, "Local LLM", "Ollama / LM Studio\nQwen3 (single shared)",
    color="#231034", edge=PURPLE, fs=11)
arrow(11.0, 6.5, 12.1, 6.5, color=PURPLE, lw=2.2)
ax.text(11.55, 6.72, "1 lock", ha="center", color=PURPLE, fontsize=8.5)

# ---------------- SQLite (left) ----------------
box(0.3, 6.0, 2.6, 1.05, "SQLite", "agent_runs · resource_stats\nscheduler_log · agent_outputs",
    color="#0f2a22", edge=GREEN, fs=11)
arrow(4.0, 6.5, 2.9, 6.5, color=GREEN)

# ---------------- Agents (bottom row) ----------------
agents = [
    ("1 · AI-Times", "YouTube / RSS →\nLLM blurbs → email"),
    ("2 · Mailman", "Gmail classify\nlabel · star · alert"),
    ("3 · Wallstreet Wolf", "yfinance 20+ stocks\nLLM commentary"),
    ("4 · Calendar Optimizer", "Google Calendar\nconflict-free day plan"),
]
xs = [0.5, 4.05, 7.6, 11.15]
AW, AY, AH = 3.0, 2.55, 1.25
for (title, sub), x in zip(agents, xs):
    box(x, AY, AW, AH, title, sub, color="#11213f", edge=ACCENT, fs=10.5)
    cx = x + AW / 2
    tx = max(4.4, min(10.6, cx))   # land on the orchestrator's bottom edge
    arrow(cx, AY + AH, tx, OY0, color=MUTED)

# external APIs row
ext = ["YouTube / RSS", "Gmail API", "Yahoo Finance", "Google Calendar"]
for label, x in zip(ext, xs):
    box(x + 0.4, 1.05, 2.2, 0.55, label, color="#1a1a2e", edge=MUTED, tcolor=MUTED, fs=8.5)
    arrow(x + 1.5, 1.6, x + 1.5, 2.55, color=MUTED, style="<|-|>")

# 5th-agent note
ax.text(7.5, 0.5,
        "Agent 4 (Calendar Optimizer) is the custom “Your Choice” agent: external API + local LLM solving a real scheduling problem.",
        ha="center", color=MUTED, fontsize=9, style="italic")

# ---------------- Legend ----------------
legend = [
    mpatches.Patch(color=ACCENT, label="control / data flow"),
    mpatches.Patch(color=PURPLE, label="serialized LLM access"),
    mpatches.Patch(color=RED, label="deadlock prevention"),
    mpatches.Patch(color=GREEN, label="persistence / UI"),
]
ax.legend(handles=legend, loc="upper left", facecolor=PANEL, edgecolor=PANEL,
          labelcolor=TEXT, fontsize=8.5, framealpha=0.95, bbox_to_anchor=(0.0, 1.0))

plt.savefig(f"{__file__.rsplit('/', 1)[0] if '/' in __file__ else '.'}/architecture.png",
            dpi=160, facecolor=BG, bbox_inches="tight")
print("wrote architecture.png")
