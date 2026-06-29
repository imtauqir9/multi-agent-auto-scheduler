# 🎤 Demo Video — Word-for-Word Narration
**Read the plain text aloud. [Bracketed text] = what to show on screen. Target: under 10 minutes.**

---

## [0:00] Intro — show the dashboard
"Hi, my name is Imran, and this is my Multi-Agent Personal Auto-Scheduling Platform.
It runs entirely on my local machine, and every bit of AI inference is done by a local
Qwen3 model through Ollama — there are no cloud LLM calls anywhere in this project.

A central orchestrator manages five agents, schedules their access to the local model,
monitors system resources, prevents deadlocks, and serves the dashboard you're looking at now.
The code is on a public GitHub repo, which I'll link in the description."

---

## [0:40] Prove the LLM is local — switch to the terminal
"First, let me prove the model is local. [run: ollama list] Here you can see Qwen3 installed
locally. [run: curl http://localhost:11434/api/tags] And the Ollama server is responding on
localhost, port 11434 — that's my own machine, not the internet.

[run: python run.py --check] This self-check confirms the platform can reach the local model,
the SQLite database is ready, and I'm tracking more than twenty stock tickers."

---

## [1:20] Architecture — show docs/architecture.png
"Here's the architecture. The orchestrator sits in the middle. On the right is the single local
LLM — single, because only one inference can run at a time. On the left is SQLite, where I store
every run, every scheduling decision, and every resource sample. Along the bottom are the five
agents and the external APIs they use. Everything inside this diagram runs on my laptop."

---

## [2:00] The technical core — deadlock prevention — show scheduler.py, then terminal
"The most interesting part is how the orchestrator schedules the shared model and prevents
deadlocks. Because agents run on a worker pool and each one needs several locks at once — the
model plus an API lock like Gmail or the network — they could deadlock through circular wait.

I prevent that two ways. First, every job grabs all of its locks in one atomic, sorted step.
Second, I use the wait-die protocol: every job has an age, and when it wants a lock another job
is holding, the older job waits while the younger one aborts and retries. Because only older jobs
ever wait, the system can never form a cycle, so it can never deadlock.

[run: pytest -q] And here are four unit tests proving exactly that — including a stress test where
two agents fight over the same two locks and always finish without hanging. All passing."

---

## [3:30] Dashboard tour — switch to the browser
"Now the dashboard. Up here is the system status — 'all systems nominal', the Qwen3 model badge,
and how many agents are running right now. These cards show live CPU, memory, thread count, and
uptime, all coming from the orchestrator.

This is the orchestration graph: the orchestrator in the center, wired to each of my five agents.
Watch what happens when an agent runs — its link lights up and animates, and its node pulses.
Below that is the scheduler panel, showing the queue, the active agent, and which locks are held
right now."

---

## [4:30] Run the agents — click each one, point at the outputs table
"Let me trigger the agents. Everything they produce shows up live in this 'Latest agent outputs'
panel at the bottom.

[click AI-Times in the sidebar — a toast pops up, its node animates] AI-Times pulls the latest AI
YouTube videos — these are real, current uploads from channels like Two Minute Papers and AI
Explained — and each title here is a clickable link to the video. The local model also writes a
one-line summary of each for the email digest.

[click Mailman] Mailman reads the inbox and the local model classifies every email. You can see
them tagged here — a production alert in red as urgent, an invoice as finance, a sale as promotion.

[click Wallstreet-Wolf] Wallstreet Wolf pulls quotes for over twenty stocks. Here's the full
watchlist — gainers tagged green, losers tagged red — and the model's market commentary on top.

[click Calendar-Optimizer] And this is my custom agent, the Calendar Optimizer. It reads today's
calendar, flags overlapping meetings — here are the conflicts in amber — and the local model writes
an optimized day plan that resolves them and protects a focus block."

---

## [6:30] Show deadlock prevention live — point at the scheduler log
"And here's the deadlock prevention working in real time. While one agent holds the model, you can
see the others logging 'deadlock avoided' — that's the wait-die protocol aborting the younger jobs.
Then, one at a time, each agent acquires the model, runs, and finishes. Nothing ever gets stuck."

---

## [7:30] Resource throttling — terminal + dashboard
"The orchestrator also protects the machine. [run a CPU-heavy command, e.g. open a few heavy apps]
When CPU load crosses my limit, watch the gauge turn red and this throttle banner appear — the
scheduler defers new model jobs until the machine recovers, and logs a 'throttled' event.
[stop the load] Once load drops, jobs resume automatically."

---

## [8:30] Persistence and wrap-up — show the logs, then the repo
"Everything you've seen is stored in SQLite — every run, every scheduling decision, every output —
and replayed here on the dashboard, so nothing is lost between restarts.

So to recap: a local orchestrator managing five agents, scheduling a single shared Qwen3 model with
real deadlock prevention and resource throttling, all on Python with a plain HTML and JavaScript
dashboard, and a hundred percent local inference. The repo and full setup instructions are linked
below. Thanks for watching!"

---

### Quick recording tips
- Have Ollama running and the dashboard open before you hit record.
- If Wallstreet shows "no quotes," just say "Yahoo is rate-limiting right now, but the agent and its
  email report work the same way" and move on — don't stall.
- Zoom the browser to ~110% and use a large terminal font so text is readable.
- Do one practice run start-to-finish to stay under 10 minutes.
