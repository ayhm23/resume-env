# server/app.py
# FastAPI app for ResumeEnv.
# Uses openenv's create_app (exposes /reset /step /state /health /ws /web).
# Adds 3 required hackathon endpoints: /tasks /grader /baseline
#
# IMPORTANT: Pass the Environment CLASS (not an instance) to create_app.
# The framework creates a fresh instance per WebSocket session via the factory pattern.

import re
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from openenv.core.env_server import create_app

from models import ResumeAction, ResumeObservation
from server.resume_environment import ResumeEnvironment, PAIRS, _ats_score, _f1, _jaccard, _clamp

# Pass the class (factory), not an instance — required by HTTPEnvServer
app: FastAPI = create_app(ResumeEnvironment, ResumeAction, ResumeObservation)

# Module-level tracker for last HTTP /step reward — used by /grader endpoint.
_last_step_reward: float = 0.5


# ─────────────────────────────────────────────────────────────────────────────
# / — Landing page UI
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ResumeEnv — OpenEnv</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet"/>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:          #0a0a0f;
      --bg2:         #0e0e16;
      --surface:     #111118;
      --surface2:    #18181f;
      --border:      rgba(255,255,255,0.07);
      --border-hi:   rgba(255,255,255,0.13);
      --text:        #f0f0f5;
      --muted:       #7a7a8c;
      --muted2:      #4a4a5a;
      --accent:      #7c6dfa;
      --accent2:     #a78bfa;
      --accent-glow: rgba(124,109,250,0.25);
      --green:       #34d399;
      --green-bg:    rgba(52,211,153,0.1);
      --green-border:rgba(52,211,153,0.25);
      --yellow:      #fbbf24;
      --yellow-bg:   rgba(251,191,36,0.1);
      --yellow-border:rgba(251,191,36,0.25);
      --red:         #f87171;
      --red-bg:      rgba(248,113,113,0.1);
      --red-border:  rgba(248,113,113,0.25);
      --radius-sm:   8px;
      --radius:      12px;
      --radius-lg:   16px;
    }

    html { scroll-behavior: smooth; }

    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }

    /* ── SCROLLBAR ── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--muted2); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--muted); }

    /* ── NAV ── */
    nav {
      position: sticky; top: 0; z-index: 100;
      height: 58px;
      display: flex; align-items: center; justify-content: space-between;
      padding: 0 32px;
      background: rgba(10,10,15,0.75);
      backdrop-filter: blur(20px) saturate(180%);
      -webkit-backdrop-filter: blur(20px) saturate(180%);
      border-bottom: 1px solid var(--border);
    }
    .logo {
      display: flex; align-items: center; gap: 9px;
      font-size: .95rem; font-weight: 700; letter-spacing: -.01em;
      color: var(--text); text-decoration: none;
    }
    .logo-icon {
      width: 30px; height: 30px; border-radius: 8px;
      background: linear-gradient(135deg, #7c6dfa, #a78bfa);
      display: flex; align-items: center; justify-content: center;
      font-size: .9rem; flex-shrink: 0;
      box-shadow: 0 0 16px var(--accent-glow);
    }
    .nav-links { display: flex; gap: 2px; }
    .nav-links a {
      padding: 5px 13px; border-radius: var(--radius-sm);
      font-size: .82rem; font-weight: 500;
      color: var(--muted); text-decoration: none;
      transition: background .15s, color .15s;
    }
    .nav-links a:hover { background: var(--surface2); color: var(--text); }
    #status-pill {
      display: flex; align-items: center; gap: 7px;
      padding: 5px 13px; border-radius: 20px;
      border: 1px solid var(--border);
      background: var(--surface);
      font-size: .75rem; font-weight: 600; color: var(--muted);
    }
    #status-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: var(--muted2);
      transition: background .4s, box-shadow .4s;
    }
    #status-dot.ok  { background: var(--green); box-shadow: 0 0 8px var(--green); }
    #status-dot.err { background: var(--red);   box-shadow: 0 0 8px var(--red); }

    /* ── HERO ── */
    .hero-wrap {
      position: relative; overflow: hidden;
      padding: 100px 24px 80px;
    }
    /* Grid pattern background */
    .hero-wrap::before {
      content: '';
      position: absolute; inset: 0;
      background-image:
        linear-gradient(var(--border) 1px, transparent 1px),
        linear-gradient(90deg, var(--border) 1px, transparent 1px);
      background-size: 40px 40px;
      mask-image: radial-gradient(ellipse 70% 60% at 50% 50%, black 40%, transparent 100%);
      -webkit-mask-image: radial-gradient(ellipse 70% 60% at 50% 50%, black 40%, transparent 100%);
    }
    /* Ambient glow */
    .hero-wrap::after {
      content: '';
      position: absolute; inset: 0;
      background: radial-gradient(ellipse 50% 45% at 50% 30%, rgba(124,109,250,0.12) 0%, transparent 70%);
      pointer-events: none;
    }
    .hero {
      max-width: 720px; margin: 0 auto;
      text-align: center; position: relative; z-index: 1;
    }
    .hero-eyebrow {
      display: inline-flex; align-items: center; gap: 7px;
      background: var(--surface2);
      border: 1px solid var(--border-hi);
      color: var(--accent2);
      font-size: .73rem; font-weight: 600;
      padding: 5px 14px; border-radius: 20px;
      margin-bottom: 28px; letter-spacing: .06em; text-transform: uppercase;
    }
    .hero-eyebrow span { font-size: .85rem; }
    .hero h1 {
      font-size: clamp(2.4rem, 5vw, 3.4rem);
      font-weight: 800; line-height: 1.1;
      letter-spacing: -.03em;
      margin-bottom: 20px;
    }
    .hero h1 .grad {
      background: linear-gradient(135deg, #a78bfa 0%, #7c6dfa 40%, #60a5fa 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .hero p {
      font-size: 1.05rem; color: var(--muted);
      max-width: 520px; margin: 0 auto 36px; line-height: 1.65;
    }
    .hero-btns { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
    .btn {
      display: inline-flex; align-items: center; gap: 7px;
      padding: 10px 22px; border-radius: var(--radius-sm);
      font-size: .88rem; font-weight: 600;
      text-decoration: none; cursor: pointer;
      transition: all .2s cubic-bezier(.34,1.56,.64,1);
      letter-spacing: -.01em;
    }
    .btn-primary {
      background: var(--accent);
      color: #fff;
      box-shadow: 0 0 0 0 var(--accent-glow);
    }
    .btn-primary:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 28px var(--accent-glow);
      background: var(--accent2);
    }
    .btn-primary:active { transform: translateY(0); }
    .btn-secondary {
      background: var(--surface2);
      color: var(--text);
      border: 1px solid var(--border-hi);
    }
    .btn-secondary:hover {
      transform: translateY(-2px);
      border-color: var(--accent);
      background: rgba(124,109,250,0.08);
      color: var(--accent2);
    }

    /* ── STATS BAR ── */
    .stats { max-width: 860px; margin: 0 auto; padding: 0 24px; }
    .stats-inner {
      display: grid; grid-template-columns: repeat(4,1fr);
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      overflow: hidden;
    }
    .stat {
      padding: 24px 20px; text-align: center;
      border-right: 1px solid var(--border);
      transition: background .2s;
    }
    .stat:last-child { border-right: none; }
    .stat:hover { background: var(--surface2); }
    .stat-val {
      font-size: 1.75rem; font-weight: 800;
      background: linear-gradient(135deg, var(--accent2), #60a5fa);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text; letter-spacing: -.03em;
    }
    .stat-val.live { background: none; -webkit-text-fill-color: var(--green); }
    .stat-label { font-size: .72rem; color: var(--muted); margin-top: 4px; letter-spacing: .03em; text-transform: uppercase; }

    /* ── SECTIONS ── */
    .section { max-width: 860px; margin: 72px auto 0; padding: 0 24px; }
    .section-title {
      font-size: .7rem; font-weight: 700;
      color: var(--muted); letter-spacing: .1em; text-transform: uppercase;
      margin-bottom: 20px;
      display: flex; align-items: center; gap: 12px;
    }
    .section-title::after {
      content: ''; flex: 1; height: 1px;
      background: linear-gradient(90deg, var(--border-hi), transparent);
    }

    /* ── TASK CARDS ── */
    .tasks { display: grid; grid-template-columns: repeat(auto-fit,minmax(250px,1fr)); gap: 16px; }
    .task-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 24px;
      cursor: default;
      transition: border-color .25s, box-shadow .25s, transform .25s;
      position: relative; overflow: hidden;
    }
    .task-card::before {
      content: '';
      position: absolute; inset: 0;
      background: radial-gradient(circle at 0% 0%, var(--accent-glow) 0%, transparent 60%);
      opacity: 0; transition: opacity .3s;
    }
    .task-card:hover::before { opacity: 1; }
    .task-card:hover {
      border-color: var(--border-hi);
      box-shadow: 0 0 0 1px var(--border-hi), 0 16px 40px rgba(0,0,0,.4);
      transform: translateY(-3px);
    }
    .task-card-top {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 14px;
    }
    .task-num {
      font-size: .7rem; font-weight: 700;
      color: var(--accent2); letter-spacing: .06em; text-transform: uppercase;
    }
    .diff-badge {
      font-size: .67rem; font-weight: 700;
      padding: 3px 10px; border-radius: 20px; letter-spacing: .04em;
    }
    .easy   { background: var(--green-bg);  color: var(--green);  border: 1px solid var(--green-border); }
    .medium { background: var(--yellow-bg); color: var(--yellow); border: 1px solid var(--yellow-border); }
    .hard   { background: var(--red-bg);    color: var(--red);    border: 1px solid var(--red-border); }
    .task-card h3 {
      font-size: 1rem; font-weight: 700;
      margin-bottom: 8px; letter-spacing: -.01em;
    }
    .task-card p { font-size: .83rem; color: var(--muted); line-height: 1.6; margin-bottom: 16px; }
    .task-meta { display: flex; gap: 7px; flex-wrap: wrap; }
    .meta-chip {
      font-family: 'Fira Code', monospace;
      font-size: .67rem; font-weight: 500;
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 5px; padding: 2px 8px; color: var(--muted);
    }

    /* ── ENDPOINT TABLE ── */
    .endpoint-table {
      width: 100%; border-collapse: collapse;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      overflow: hidden;
    }
    .endpoint-table thead { background: var(--surface2); }
    .endpoint-table th {
      padding: 12px 18px; text-align: left;
      font-size: .67rem; font-weight: 600;
      color: var(--muted); letter-spacing: .1em; text-transform: uppercase;
      border-bottom: 1px solid var(--border);
    }
    .endpoint-table td {
      padding: 12px 18px;
      border-bottom: 1px solid var(--border);
      font-size: .83rem; vertical-align: middle;
      color: var(--muted);
      transition: background .15s;
    }
    .endpoint-table tr:last-child td { border-bottom: none; }
    .endpoint-table tbody tr:hover td { background: var(--surface2); }
    .method {
      font-family: 'Fira Code', monospace;
      font-size: .68rem; font-weight: 600;
      padding: 3px 9px; border-radius: 5px;
      letter-spacing: .04em; display: inline-block;
    }
    .get  { background: rgba(96,165,250,0.12); color: #60a5fa; border: 1px solid rgba(96,165,250,0.2); }
    .post { background: var(--green-bg);        color: var(--green); border: 1px solid var(--green-border); }
    .path {
      font-family: 'Fira Code', monospace;
      font-size: .83rem; color: var(--accent2);
      text-decoration: none;
    }
    .path:hover { text-decoration: underline; }

    /* ── CODE BLOCK ── */
    .code-wrap {
      position: relative;
      background: #080810;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      overflow: hidden;
    }
    .code-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 10px 18px;
      background: var(--surface2);
      border-bottom: 1px solid var(--border);
    }
    .code-lang {
      font-family: 'Fira Code', monospace;
      font-size: .7rem; color: var(--muted); letter-spacing: .06em;
    }
    .code-dots { display: flex; gap: 6px; }
    .code-dots span {
      width: 11px; height: 11px; border-radius: 50%;
      background: var(--muted2);
    }
    .code-dots span:nth-child(1) { background: #ff5f57; }
    .code-dots span:nth-child(2) { background: #febc2e; }
    .code-dots span:nth-child(3) { background: #28c840; }
    .code-block {
      padding: 22px 22px 22px;
      font-family: 'Fira Code', monospace;
      font-size: .8rem; line-height: 1.8;
      color: #c9d1d9;
      overflow-x: auto;
      position: relative;
    }
    /* Syntax colours */
    .code-block .c  { color: #4a4a64; }
    .code-block .k  { color: #79c0ff; }
    .code-block .s  { color: #a5d6ff; }
    .code-block .v  { color: #ff7b72; }
    .code-block .p  { color: #d2a8ff; }
    .copy-code {
      font-family: 'Inter', sans-serif;
      font-size: .7rem; font-weight: 500;
      padding: 4px 12px;
      border: 1px solid var(--border-hi);
      border-radius: var(--radius-sm);
      background: var(--surface);
      color: var(--muted);
      cursor: pointer;
      transition: all .15s;
    }
    .copy-code:hover { background: var(--accent); color: #fff; border-color: var(--accent); }
    .copy-code.copied { background: var(--green-bg); color: var(--green); border-color: var(--green-border); }

    /* ── FOOTER ── */
    footer {
      max-width: 860px; margin: 80px auto 48px;
      padding: 28px 24px 0;
      border-top: 1px solid var(--border);
      display: flex; align-items: center;
      justify-content: space-between; flex-wrap: wrap; gap: 12px;
    }
    .footer-left { font-size: .78rem; color: var(--muted2); }
    .footer-links { display: flex; gap: 20px; }
    .footer-links a {
      font-size: .78rem; color: var(--muted);
      text-decoration: none; transition: color .15s;
    }
    .footer-links a:hover { color: var(--accent2); }

    /* ── RESPONSIVE ── */
    @media (max-width: 600px) {
      nav { padding: 0 16px; }
      .nav-links { display: none; }
      .hero-wrap { padding: 70px 16px 60px; }
      .stats-inner { grid-template-columns: repeat(2,1fr); }
      .stat { border-bottom: 1px solid var(--border); }
      .section { padding: 0 16px; }
      footer { padding: 24px 16px 0; }
    }
  </style>
</head>
<body>

<!-- NAV -->
<nav>
  <a class="logo" href="/">
    <div class="logo-icon">📄</div>
    ResumeEnv
  </a>
  <div class="nav-links">
    <a href="#tasks">Tasks</a>
    <a href="#api">API</a>
    <a href="#quickstart">Quick&nbsp;Start</a>
    <a href="/docs">Swagger</a>
  </div>
  <div id="status-pill">
    <div id="status-dot"></div>
    <span id="status-text">Checking…</span>
  </div>
</nav>

<!-- HERO -->
<div class="hero-wrap">
  <div class="hero">
    <div class="hero-eyebrow"><span>🏆</span> OpenEnv Hackathon&nbsp;2026</div>
    <h1>Resume Optimizer<br/><span class="grad">AI Environment</span></h1>
    <p>An AI agent reads a job description and a candidate resume, then optimises the resume and cover letter to maximise ATS match rate.</p>
    <div class="hero-btns">
      <a href="/docs" class="btn btn-primary">⚡&nbsp;&nbsp;Try the API</a>
      <a href="#quickstart" class="btn btn-secondary">📋&nbsp;&nbsp;Quick Start</a>
    </div>
  </div>
</div>

<!-- STATS -->
<div class="stats">
  <div class="stats-inner">
    <div class="stat"><div class="stat-val">3</div><div class="stat-label">Tasks</div></div>
    <div class="stat"><div class="stat-val">0 – 1</div><div class="stat-label">Reward Range</div></div>
    <div class="stat"><div class="stat-val">4</div><div class="stat-label">Max Steps</div></div>
    <div class="stat"><div class="stat-val live" id="baseline-score">—</div><div class="stat-label">Baseline Score</div></div>
  </div>
</div>

<!-- TASKS -->
<div class="section" id="tasks">
  <div class="section-title">Tasks</div>
  <div class="tasks">
    <div class="task-card">
      <div class="task-card-top"><span class="task-num">Task&nbsp;01</span><span class="diff-badge easy">Easy</span></div>
      <h3>Keyword Extraction</h3>
      <p>Extract hard skills, soft skills, and required experience years directly from a job description.</p>
      <div class="task-meta">
        <span class="meta-chip">max_steps: 1</span>
        <span class="meta-chip">extract_keywords</span>
      </div>
    </div>
    <div class="task-card">
      <div class="task-card-top"><span class="task-num">Task&nbsp;02</span><span class="diff-badge medium">Medium</span></div>
      <h3>Bullet Rewrite</h3>
      <p>Rewrite a resume bullet to maximise ATS score — strong action verbs and quantified impact required.</p>
      <div class="task-meta">
        <span class="meta-chip">max_steps: 1</span>
        <span class="meta-chip">rewrite_bullet</span>
      </div>
    </div>
    <div class="task-card">
      <div class="task-card-top"><span class="task-num">Task&nbsp;03</span><span class="diff-badge hard">Hard</span></div>
      <h3>Full Application Pack</h3>
      <p>4-step multi-turn episode: rewrite summary → experience → skills → write a full tailored cover letter.</p>
      <div class="task-meta">
        <span class="meta-chip">max_steps: 4</span>
        <span class="meta-chip">rewrite_summary</span>
        <span class="meta-chip">write_cover_letter</span>
      </div>
    </div>
  </div>
</div>

<!-- API -->
<div class="section" id="api">
  <div class="section-title">API Endpoints</div>
  <table class="endpoint-table">
    <thead>
      <tr><th>Method</th><th>Path</th><th>Description</th></tr>
    </thead>
    <tbody>
      <tr><td><span class="method get">GET</span></td><td><a class="path" href="/health" target="_blank">/health</a></td><td>Liveness check — returns <code>{"status":"healthy"}</code></td></tr>
      <tr><td><span class="method get">GET</span></td><td><a class="path" href="/tasks" target="_blank">/tasks</a></td><td>List all tasks with action schemas</td></tr>
      <tr><td><span class="method post">POST</span></td><td><span class="path">/reset</span></td><td>Start a new episode — body: <code>{"task_id":"task1_keyword_extraction"}</code></td></tr>
      <tr><td><span class="method post">POST</span></td><td><span class="path">/step</span></td><td>Submit an action, receive reward &amp; observation</td></tr>
      <tr><td><span class="method get">GET</span></td><td><a class="path" href="/state" target="_blank">/state</a></td><td>Current episode state (step_count, episode_id)</td></tr>
      <tr><td><span class="method get">GET</span></td><td><a class="path" href="/grader" target="_blank">/grader</a></td><td>Last episode grader scores</td></tr>
      <tr><td><span class="method post">POST</span></td><td><span class="path">/baseline</span></td><td>Run deterministic rule-based baseline on all 3 tasks</td></tr>
      <tr><td><span class="method get">GET</span></td><td><a class="path" href="/docs" target="_blank">/docs</a></td><td>Interactive Swagger UI</td></tr>
    </tbody>
  </table>
</div>

<!-- QUICK START -->
<div class="section" id="quickstart">
  <div class="section-title">Quick Start</div>
  <div class="code-wrap">
    <div class="code-header">
      <div class="code-dots"><span></span><span></span><span></span></div>
      <span class="code-lang">bash</span>
      <button class="copy-code" id="copy-btn" onclick="copyCode('code1')">Copy</button>
    </div>
    <div class="code-block" id="code1"><span class="c"># 1. Health check</span>
<span class="k">curl</span> <span class="s">https://ayhm23-resume-env.hf.space/health</span>

<span class="c"># 2. Start Task 1 episode</span>
<span class="k">curl</span> -X POST <span class="s">https://ayhm23-resume-env.hf.space/reset</span> \
  -H <span class="v">"Content-Type: application/json"</span> \
  -d <span class="p">'{"task_id":"task1_keyword_extraction"}'</span>

<span class="c"># 3. Submit action</span>
<span class="k">curl</span> -X POST <span class="s">https://ayhm23-resume-env.hf.space/step</span> \
  -H <span class="v">"Content-Type: application/json"</span> \
  -d <span class="p">'{"action":{"action_type":"extract_keywords","hard_skills":["SQL","Python","Tableau"],"soft_skills":["communication"],"experience_years":5}}'</span>

<span class="c"># 4. Python inference agent</span>
<span class="k">python</span> inference.py</div>
  </div>
</div>

<!-- FOOTER -->
<footer>
  <div class="footer-left">ResumeEnv &copy; 2026 &mdash; OpenEnv Hackathon</div>
  <div class="footer-links">
    <a href="/docs">Swagger</a>
    <a href="/health">Health</a>
    <a href="/tasks">Tasks</a>
    <a href="/grader">Grader</a>
  </div>
</footer>

<script>
  // Live health check
  async function checkHealth() {
    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('status-text');
    try {
      const r = await fetch('/health');
      if (r.ok) {
        dot.className = 'ok'; txt.textContent = 'Live';
      } else {
        dot.className = 'err'; txt.textContent = 'Error ' + r.status;
      }
    } catch {
      dot.className = 'err'; txt.textContent = 'Offline';
    }
  }

  // Fetch baseline score
  async function fetchBaseline() {
    try {
      const r = await fetch('/baseline', {method:'POST'});
      if (r.ok) {
        const d = await r.json();
        const el = document.getElementById('baseline-score');
        if (d.overall_average_score !== undefined) {
          el.textContent = d.overall_average_score.toFixed(2);
        }
      }
    } catch {}
  }

  // Copy code block text
  function copyCode(id) {
    const el = document.getElementById(id);
    const text = el.innerText;
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById('copy-btn');
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
    });
  }

  checkHealth();
  fetchBaseline();
  setInterval(checkHealth, 30000);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# /tasks — list all tasks + their action schemas
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/tasks")
def get_tasks():
    return {
        "tasks": [
            {
                "id": "task1_keyword_extraction",
                "name": "Extract Key Skills from Job Description",
                "difficulty": "easy",
                "max_steps": 1,
                "reward_range": [0.0, 1.0],
                "description": "Given a JD, extract hard skills, soft skills, and required experience years.",
                "action_schema": {
                    "action_type": "'extract_keywords'",
                    "hard_skills": "List[str]  e.g. ['SQL','Python','Tableau']",
                    "soft_skills": "List[str]  e.g. ['stakeholder communication']",
                    "experience_years": "int  e.g. 5",
                },
            },
            {
                "id": "task2_bullet_rewrite",
                "name": "Rewrite Resume Bullet for ATS",
                "difficulty": "medium",
                "max_steps": 1,
                "reward_range": [0.0, 1.0],
                "description": "Rewrite a resume bullet to maximise ATS score. Add numbers and strong action verbs.",
                "action_schema": {
                    "action_type": "'rewrite_bullet'",
                    "rewritten_bullet": "str  e.g. 'Developed Tableau dashboards tracking 12 KPIs...'",
                },
            },
            {
                "id": "task3_full_application",
                "name": "Full Application Pack for Senior Role",
                "difficulty": "hard",
                "max_steps": 4,
                "reward_range": [0.0, 1.0],
                "description": (
                    "Build a complete tailored application in 4 sequential steps: "
                    "rewrite_summary → rewrite_experience → update_skills → write_cover_letter."
                ),
                "action_schema": {
                    "action_type": "one of: 'rewrite_summary' | 'rewrite_experience' | 'update_skills' | 'write_cover_letter'",
                    "content": "str  your output for this step",
                },
            },
        ]
    }


# ─────────────────────────────────────────────────────────────────────────────
# /grader — return last episode grader scores
# ─────────────────────────────────────────────────────────────────────────────

@app.middleware("http")
async def _track_step_reward(request: Request, call_next):
    """Capture reward from POST /step responses so /grader can return final_score."""
    global _last_step_reward
    response = await call_next(request)
    if request.url.path == "/step" and request.method == "POST":
        import json
        from starlette.responses import Response
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        try:
            data = json.loads(body)
            r = data.get("reward")
            if r is not None:
                _last_step_reward = float(r)
        except Exception:
            pass
        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    return response


@app.get("/grader")
def get_grader():
    """
    Grader details and last episode final_score.
    full grader breakdown is also returned inline in each /step observation's metadata.
    """
    return {
        "final_score": round(_last_step_reward, 4),
        "info": "Grader results are returned inline in each /step observation.",
        "fields": {
            "observation.reward": "Float in [0.0, 1.0] — step reward",
            "observation.current_score": "Float in [0.0, 1.0] — episode score so far",
            "observation.metadata": "Detailed grader breakdown (per-component scores)",
            "observation.done": "True when the episode is complete",
        },
        "task_graders": {
            "task1_keyword_extraction": {
                "weights": {"hard_skill_f1": 0.60, "soft_skill_jaccard": 0.25, "experience_score": 0.15},
            },
            "task2_bullet_rewrite": {
                "weights": {"ats_delta": 0.40, "semantic_preservation": 0.30, "quality_score": 0.30},
            },
            "task3_full_application": {
                "weights": {"resume_ats": 0.35, "cover_letter_relevance": 0.25, "keyword_coverage": 0.25, "format_score": 0.15},
                "sub_rewards": "Intermediate partial rewards given after each of the 4 steps",
            },
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# /baseline — deterministic rule-based baseline, no LLM needed
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/baseline")
def run_baseline():
    """
    Rule-based baseline agent — no LLM, deterministic, always completes without error.
    Runs one episode per task on PAIRS[0] and returns grader scores.
    """
    pair = PAIRS[0]
    jd   = pair["jd"]
    results = {}

    # ── Task 1: extract capitalised tokens from JD as hard skills ──
    hard_baseline = list({
        w for w in re.findall(r'\b[A-Z][a-zA-Z+#\.]{1,12}\b', jd)
        if w not in {"We", "Must", "The", "Strong", "Required", "Seeking",
                     "Hiring", "Experience", "Proficiency", "Looking"}
    })[:6]

    hard_f1  = _f1(hard_baseline, pair["gt_hard"])
    soft_jac = _jaccard(["communication", "collaboration"], pair["gt_soft"])
    baseline_years = max(int(pair["gt_years"]) - 1, 1)  # baseline guesses 1 year short
    exp_score = max(0.0, 1.0 - abs(baseline_years - pair["gt_years"]) / max(pair["gt_years"], 1))
    t1_score = _clamp(round(0.60 * hard_f1 + 0.25 * soft_jac + 0.15 * exp_score, 4))
    results["task1_keyword_extraction"] = {
        "score": t1_score,
        "hard_f1": hard_f1, "soft_jaccard": soft_jac,
    }

    # ── Task 2: append JD keywords to original bullet ──
    original = pair["resume"]["experience"][0]["bullets"][0]
    kws = hard_baseline[:3]
    rewritten = (
        f"Developed and delivered {original.lower().rstrip('.')} "
        f"using {', '.join(kws)}, improving team output by 25%."
    )
    ats_b = _ats_score(original, jd)
    ats_a = _ats_score(rewritten, jd)
    headroom = max(1.0 - ats_b, 0.01)
    ats_d = min(max((ats_a - ats_b) / headroom, 0.0), 1.0)
    t2_score = _clamp(round(0.40 * ats_d + 0.30 * 0.5 + 0.30 * 1.0, 4))   # quality=1 (has number + verb)
    results["task2_bullet_rewrite"] = {
        "score": t2_score,
        "ats_before": ats_b, "ats_after": ats_a,
    }

    # ── Task 3: assemble cover letter from base resume ──
    resume   = pair["resume"]
    base_txt = " ".join(resume.get("skills", []))
    cover    = (
        f"Dear Hiring Manager,\n\n"
        f"I am excited to apply for this role. With experience in {base_txt}, "
        f"I am confident I can contribute meaningfully.\n\n"
        f"Thank you for your time.\n\nSincerely,\n{resume['name']}"
    )
    from server.resume_environment import _resume_to_text, _kw_coverage
    resume_text = _resume_to_text(resume)
    ats3  = _ats_score(resume_text, jd)
    cov_r = _ats_score(cover, jd)
    kw_c  = _kw_coverage(resume_text + " " + cover, pair["gt_hard"])
    fmt   = 1.0  # base resume has all sections
    t3_score = _clamp(round(0.35 * ats3 + 0.25 * cov_r + 0.25 * kw_c + 0.15 * fmt, 4))
    results["task3_full_application"] = {
        "score": t3_score,
        "resume_ats": ats3, "cover_relevance": cov_r, "keyword_coverage": kw_c,
    }

    overall = round(sum(r["score"] for r in results.values()) / 3, 4)
    return {
        "baseline_agent": "rule-based (no LLM, deterministic)",
        "results": results,
        "overall_average_score": overall,
    }


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
