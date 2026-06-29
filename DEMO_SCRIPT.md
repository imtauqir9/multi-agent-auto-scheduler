# 🎬 Demo Video Script — Multi-Agent Auto-Scheduling Platform
**Target length: ≤ 10 minutes.** Times are cumulative. Keep the energy up and *show, don't tell*.

---

## 0:00 – 0:45 · Intro & the pitch
**On screen:** your face / title slide → the dashboard.

> "Hi, I'm Imran. This is a Multi-Agent Personal Auto-Scheduling Platform that runs
> **entirely on my local machine**. A central orchestrator manages five agents, schedules
> access to a **local Qwen3 model through Ollama**, monitors system resources, and prevents
> deadlocks — all surfaced on a live dashboard. **No cloud LLM is used anywhere.**"

✅ *Mention the GitHub repo URL and that it's public.*

---

## 0:45 – 1:45 · Proof that the LLM is local
**On screen:** terminal.

```bash
ollama list            # show qwen3 is pulled
curl http://localhost:11434/api/tags   # local server responding
python run.py --check  # platform self-check
```
> "The only model client in the codebase points at `localhost:11434`. The self-check confirms
> Qwen3 is reachable, the SQLite database is ready, and 22 tickers are configured."

✅ *Open `core/llm.py` for 5 seconds — point out there are no hosted-API imports.*

---

## 1:45 – 3:15 · The orchestrator & deadlock prevention (the technical core)
**On screen:** `orchestrator/scheduler.py`, then the terminal.

> "The local LLM is a single shared resource, so agents queue for it by priority. The
> interesting part is **deadlock prevention**. With multiple workers needing multiple locks,
> you can get circular wait. I prevent it two ways: **canonical lock ordering**, and the
> **wait–die protocol** — older transactions wait, younger ones abort and retry. The wait-for
> graph can never cycle."

Run the tests live:
```bash
pytest -q
```
> "These four tests prove it: disjoint locks, wait–die abort, wait-then-acquire, and a
> contention stress test where two agents fight over the same two locks and always finish."

---

## 3:15 – 4:15 · Start the platform & tour the dashboard
**On screen:** `python run.py` → browser at `http://127.0.0.1:8000`.

> "Starting the orchestrator boots the resource monitor, the scheduler workers, and the cron
> triggers. On the dashboard: live CPU/RAM/disk gauges with throttle thresholds, the scheduler
> panel showing the queue and **which locks are currently held**, the five agent cards, and
> live scheduler + run logs."

✅ *Point to the green "LLM: qwen3 ● online" badge.*

---

## 4:15 – 5:30 · Agent 1 & 2 — AI-Times and Mailman
**On screen:** click **Run now** on AI-Times, then Mailman.

> "AI-Times pulls the latest AI YouTube videos, and Qwen3 writes a one-line 'why it matters'
> for each, then emails an HTML digest."

Open the generated email (inbox or `data/outbox/`).

> "Mailman reads unread Gmail, and the **local model classifies** each email — urgent, finance,
> newsletter, and so on — then labels and stars it. Here's the urgent-mail alert it produced."

✅ *Show a labelled/starred email in Gmail if live, or the classification output on the dashboard.*

---

## 5:30 – 6:45 · Agent 3 — Wallstreet Wolf
**On screen:** click **Run now** on Wallstreet-Wolf.

> "Wallstreet Wolf pulls quotes for 20-plus stocks from Yahoo Finance, and the local model
> writes the market commentary — biggest movers, sector patterns. Here's the daily report."

Open the report email; scroll the colored gainer/loser table.

---

## 6:45 – 8:15 · Agent 4 — Calendar Optimizer (the custom agent)
**On screen:** click **Run now** on Calendar-Optimizer.

> "This is my custom agent and the real problem it solves: messy days. It reads today's Google
> Calendar, **deterministically detects conflicts** — see these two overlapping meetings — then
> asks Qwen3 to produce an optimized plan that resolves overlaps, adds buffers, and protects a
> 90-minute focus block."

Show the optimized plan email / dashboard output.

---

## 8:15 – 9:15 · Resource monitoring & throttling in action
**On screen:** a CPU stress command + the dashboard.

```bash
# generate load so the throttle visibly kicks in
python -c "while True: pass" &   # (a couple of these)
```
> "When CPU crosses the limit, watch the gauge go red and the **throttle banner** appear — the
> scheduler defers LLM jobs until the machine recovers, logging a `throttled` event. This is the
> orchestrator protecting the host."

✅ *Kill the load; show jobs resume.*

---

## 9:15 – 10:00 · Architecture, persistence & wrap-up
**On screen:** `docs/architecture.png`, then the SQLite logs on the dashboard.

> "Everything is persisted to SQLite — every run, schedule decision, and output you saw is
> stored and replayed on the dashboard. Here's the architecture: orchestrator in the middle,
> the single local LLM serialized on the right, SQLite on the left, the five agents and their
> external APIs below. Python 3.12, FastAPI, plain HTML/JS, 100% local inference. Repo's in the
> description — thanks for watching!"

---

## Pre-record checklist
- [ ] `ollama serve` running and `qwen3` pulled
- [ ] `.env` filled (or accept demo mode) — decide before recording
- [ ] Gmail / Calendar consent already completed (so no OAuth popup mid-demo)
- [ ] Browser zoomed for readability; terminal font large
- [ ] Dashboard open and agents idle at the start
- [ ] Repo pushed and **public** — double-check the link works in an incognito window
- [ ] Total runtime under 10:00
