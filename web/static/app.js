// Mission-Control dashboard — plain vanilla JS, polls the FastAPI backend.
"use strict";

const $ = (id) => document.getElementById(id);
const SVGNS = "http://www.w3.org/2000/svg";

const AGENT_ICON = {
  "AI-Times": "▶",
  "Mailman": "✉",
  "Wallstreet-Wolf": "$",
  "Calendar-Optimizer": "🗓",
};
const icon = (name) => AGENT_ICON[name] || "◆";

function fmtTime(ts) {
  if (!ts) return "–";
  return new Date(ts * 1000).toLocaleTimeString();
}
function fmtUptime(s) {
  if (s == null) return "0m";
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${m}m`;
}
function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}
function gaugeColor(pct, limit) {
  if (pct >= limit) return "var(--red)";
  if (pct >= limit * 0.75) return "var(--amber)";
  return "var(--accent)";
}

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; }, 2400);
  setTimeout(() => t.remove(), 2900);
}

async function runAgent(name) {
  toast(`▶ ${name} started — working…`);
  try { await fetch(`/api/run/${encodeURIComponent(name)}`, { method: "POST" }); }
  catch (e) { console.error(e); }
  refresh();
}
window.runAgent = runAgent;

/* ---------------- sidebar ---------------- */
function renderSidebar(agents, llmOnline, running) {
  $("side-llm-dot").className = "dot " + (llmOnline ? "dot-idle online" : "dot-idle");
  const wrap = $("side-agents");
  wrap.innerHTML = "";
  agents.forEach((a) => {
    const cls = running.has(a.name) ? "dot-running" : "dot-" + a.last_status;
    const row = document.createElement("div");
    row.className = "side-item";
    row.title = "Run " + a.name;
    row.onclick = () => runAgent(a.name);
    row.innerHTML = `<span class="side-ico">${icon(a.name)}</span>
                     <span class="side-name">${a.name}</span>
                     <span class="dot ${cls}"></span>`;
    wrap.appendChild(row);
  });
}

/* ---------------- orchestration graph ---------------- */
function el(tag, attrs, text) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  return e;
}
function renderGraph(agents, running) {
  const svg = $("graph");
  svg.innerHTML = "";

  // gradient for the orchestrator node
  const defs = el("defs", {});
  const grad = el("linearGradient", { id: "orchGrad", x1: "0", y1: "0", x2: "1", y2: "1" });
  grad.appendChild(el("stop", { offset: "0", "stop-color": "#7c6cf6" }));
  grad.appendChild(el("stop", { offset: "1", "stop-color": "#6c5ce7" }));
  defs.appendChild(grad);
  svg.appendChild(defs);

  const ox = 480, oy = 60;
  const n = agents.length;
  const left = 140, right = 820;
  const xs = n === 1 ? [480] : agents.map((_, i) => left + i * ((right - left) / (n - 1)));
  const ay = 232;

  // links first (under nodes)
  agents.forEach((a, i) => {
    const x = xs[i];
    const active = running.has(a.name);
    const path = el("path", {
      d: `M${ox},${oy + 24} C${ox},150 ${x},150 ${x},${ay - 24}`,
      class: "glink" + (active ? " active" : ""),
    });
    svg.appendChild(path);
  });

  // orchestrator node
  svg.appendChild(el("text", { x: ox, y: 20, "text-anchor": "middle", class: "gorch-label" }, "Orchestrator"));
  svg.appendChild(el("circle", { cx: ox, cy: oy, r: 26, class: "gorch-ring" }));
  svg.appendChild(el("text", { x: ox, y: oy + 6, "text-anchor": "middle", fill: "#fff", "font-size": "18" }, "◈"));

  // agent nodes
  agents.forEach((a, i) => {
    const x = xs[i];
    const state = running.has(a.name) ? "running" : a.last_status;
    svg.appendChild(el("circle", { cx: x, cy: ay, r: 24, class: "gnode-ring " + state }));
    svg.appendChild(el("text", { x: x, y: ay + 6, "text-anchor": "middle", class: "gnode-core" }, icon(a.name)));
    const short = a.name.replace("-Optimizer", "").replace("Wallstreet-", "");
    svg.appendChild(el("text", { x: x, y: ay + 44, "text-anchor": "middle", class: "gnode-label" }, short));
  });
}

/* ---------------- agent cards ---------------- */
function renderAgents(agents, running) {
  const wrap = $("agents");
  wrap.innerHTML = "";
  agents.forEach((a) => {
    const cls = running.has(a.name) ? "dot-running" : "dot-" + a.last_status;
    const div = document.createElement("div");
    div.className = "agent";
    div.innerHTML = `
      <div class="agent-head">
        <span class="agent-name"><span class="dot ${cls}"></span>${a.name}</span>
        <span class="tag gray">prio ${a.priority}</span>
      </div>
      <div class="agent-desc">${a.description}</div>
      <div class="agent-meta">Locks: ${(a.resources || []).join(", ") || "llm"}</div>
      <div class="agent-meta">Last: ${a.last_summary || "—"} (${fmtTime(a.last_run_ts)})</div>
      <button class="run-btn" onclick="runAgent('${a.name}')">▶ Run now</button>`;
    wrap.appendChild(div);
  });
}

function renderRows(tableId, rows, cols) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = "";
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = cols(r);
    tbody.appendChild(tr);
  });
}

/* ---------------- main refresh ---------------- */
async function refresh() {
  try {
    const [status, schedule, runs, outputs] = await Promise.all([
      fetch("/api/status").then((r) => r.json()),
      fetch("/api/schedule").then((r) => r.json()),
      fetch("/api/runs").then((r) => r.json()),
      fetch("/api/outputs").then((r) => r.json()),
    ]);

    const running = new Set(status.scheduler.active || []);
    const ov = status.overview || {};
    const res = status.resources;

    // top bar + model
    $("model-pill").textContent = `${status.llm.model} · local`;
    $("side-model").textContent = `${status.llm.model} · local`;
    if (status.llm.available) {
      $("health-pill").className = "pill pill-green";
      $("health-pill").textContent = "● All systems nominal";
    } else {
      $("health-pill").className = "pill pill-red";
      $("health-pill").textContent = "● LLM offline";
    }
    $("running-pill").textContent = `${ov.agents_running || 0} running`;
    $("graph-running").textContent = `${ov.agents_running || 0} running`;
    $("top-meta").textContent = `${status.llm.base_url.replace(/^https?:\/\//, "")} · uptime ${fmtUptime(ov.uptime_seconds)} · ${ov.threads || "–"} threads`;

    // hero
    $("greeting").textContent = greeting();
    $("hero-sub").textContent = `● local inference · ${status.llm.model} via Ollama`;
    const now = new Date();
    $("clock").textContent = now.toLocaleTimeString();
    $("date").textContent = now.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });

    // stat cards
    $("st-agents").textContent = ov.agents_running || 0;
    $("st-agents-sub").textContent = `${ov.agents_managed || 0} managed`;
    $("st-cpu").textContent = res.cpu_pct.toFixed(0) + "%";
    $("st-ram").textContent = res.ram_pct.toFixed(0) + "%";
    $("st-threads").textContent = ov.threads ?? "–";
    $("st-uptime").textContent = fmtUptime(ov.uptime_seconds);
    const cb = $("st-cpu-bar"); cb.style.width = Math.min(res.cpu_pct, 100) + "%"; cb.style.background = gaugeColor(res.cpu_pct, res.limits.cpu);
    const rb = $("st-ram-bar"); rb.style.width = Math.min(res.ram_pct, 100) + "%"; rb.style.background = gaugeColor(res.ram_pct, res.limits.ram);

    // throttle banner
    const throttle = $("throttle");
    if (res.overloaded) { throttle.classList.remove("hidden"); throttle.textContent = "⏳ Throttling LLM jobs — " + res.throttle_reason; }
    else throttle.classList.add("hidden");

    // scheduler panel
    const s = status.scheduler;
    $("sched-queued").textContent = s.queued;
    $("sched-active").textContent = (s.active && s.active.length) ? s.active.join(", ") : "idle";
    $("sched-workers").textContent = s.workers;
    const locks = Object.entries(s.held_resources || {}).map(([r, a]) => `${r}→${a}`).join(", ");
    $("sched-locks").textContent = locks || "none";

    // graph + sidebar + cards
    renderSidebar(status.agents, status.llm.available, running);
    renderGraph(status.agents, running);
    renderAgents(status.agents, running);

    // logs
    renderRows("schedule-log", schedule, (r) =>
      `<td>${fmtTime(r.ts)}</td><td>${r.agent}</td><td><span class="tag">${r.event}</span></td><td>${r.detail || ""}</td>`);
    renderRows("runs-log", runs, (r) =>
      `<td>${r.agent}</td><td><span class="dot dot-${r.status}"></span> ${r.status}</td><td>${r.summary || ""}</td><td>${r.duration_s ? r.duration_s + "s" : "–"}</td>`);
    const TAG_CLASS = { gainer: "green", success: "green", loser: "red", urgent: "red", conflict: "amber" };
    renderRows("outputs", outputs, (r) => {
      const meta = r.meta || "";
      const isLink = meta.startsWith("http");
      const title = isLink
        ? `<a href="${meta}" target="_blank" rel="noopener">${r.title || ""}</a>`
        : (r.title || "");
      let tag, cls;
      if (isLink) { tag = "▶ video"; cls = ""; }
      else { tag = meta; cls = TAG_CLASS[meta] || "gray"; }
      return `<td>${r.agent}</td><td>${title}</td><td>${r.body || ""}</td><td><span class="tag ${cls}">${tag}</span></td>`;
    });
  } catch (e) {
    console.error("refresh failed", e);
  }
}

refresh();
setInterval(refresh, 3000);
// tick the clock every second for a live feel
setInterval(() => {
  const now = new Date();
  const c = $("clock"); if (c) c.textContent = now.toLocaleTimeString();
}, 1000);
