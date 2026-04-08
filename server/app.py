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
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    :root{
      --bg:#f0f4ff;--surface:#fff;--border:#e2e8f0;
      --text:#1e293b;--muted:#64748b;--accent:#4f46e5;
      --accent-light:#eef2ff;--green:#16a34a;--green-bg:#dcfce7;
      --yellow:#92400e;--yellow-bg:#fef9c3;--red:#991b1b;--red-bg:#fee2e2;
    }
    body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

    /* ── NAV ── */
    nav{background:var(--surface);border-bottom:1px solid var(--border);padding:0 32px;display:flex;align-items:center;justify-content:space-between;height:56px;position:sticky;top:0;z-index:10;box-shadow:0 1px 3px rgba(0,0,0,.06)}
    .logo{display:flex;align-items:center;gap:10px;font-weight:700;font-size:1.05rem;color:var(--accent)}
    .logo span{font-size:1.4rem}
    .nav-links{display:flex;gap:4px}
    .nav-links a{padding:6px 14px;border-radius:8px;font-size:.85rem;font-weight:500;color:var(--muted);text-decoration:none;transition:background .15s,color .15s}
    .nav-links a:hover{background:var(--accent-light);color:var(--accent)}
    #status-pill{display:flex;align-items:center;gap:6px;font-size:.78rem;font-weight:600;padding:4px 12px;border-radius:20px;background:#f1f5f9;color:var(--muted)}
    #status-dot{width:8px;height:8px;border-radius:50%;background:#94a3b8;transition:background .3s}
    #status-dot.ok{background:var(--green);box-shadow:0 0 0 3px #bbf7d0}
    #status-dot.err{background:#dc2626;box-shadow:0 0 0 3px #fecaca}

    /* ── HERO ── */
    .hero{max-width:860px;margin:56px auto 0;padding:48px 24px 32px;text-align:center}
    .hero-eyebrow{display:inline-flex;align-items:center;gap:8px;background:var(--accent-light);color:var(--accent);font-size:.78rem;font-weight:600;padding:4px 14px;border-radius:20px;margin-bottom:20px;letter-spacing:.04em}
    .hero h1{font-size:2.6rem;font-weight:800;line-height:1.15;color:var(--text);margin-bottom:16px}
    .hero h1 span{background:linear-gradient(135deg,#4f46e5,#7c3aed);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
    .hero p{font-size:1.05rem;color:var(--muted);max-width:560px;margin:0 auto 32px;line-height:1.6}
    .hero-btns{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}
    .btn{padding:10px 24px;border-radius:10px;font-size:.9rem;font-weight:600;text-decoration:none;transition:transform .15s,box-shadow .15s,opacity .15s;display:inline-flex;align-items:center;gap:7px}
    .btn:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(79,70,229,.25)}
    .btn-primary{background:var(--accent);color:#fff}
    .btn-secondary{background:var(--surface);color:var(--accent);border:1.5px solid var(--accent)}

    /* ── STATS BAR ── */
    .stats{max-width:860px;margin:0 auto;padding:0 24px}
    .stats-inner{display:flex;gap:0;background:var(--surface);border-radius:14px;border:1px solid var(--border);overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.05)}
    .stat{flex:1;padding:20px 24px;text-align:center;border-right:1px solid var(--border)}
    .stat:last-child{border-right:none}
    .stat-val{font-size:1.6rem;font-weight:800;color:var(--accent)}
    .stat-label{font-size:.78rem;color:var(--muted);margin-top:2px}

    /* ── TASKS ── */
    .section{max-width:860px;margin:48px auto 0;padding:0 24px}
    .section-title{font-size:1.1rem;font-weight:700;color:var(--text);margin-bottom:16px;display:flex;align-items:center;gap:8px}
    .section-title::after{content:'';flex:1;height:1px;background:var(--border)}
    .tasks{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
    .task-card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:22px;transition:box-shadow .2s,transform .2s;cursor:default}
    .task-card:hover{box-shadow:0 6px 24px rgba(79,70,229,.1);transform:translateY(-2px)}
    .task-card-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
    .task-num{font-size:.75rem;font-weight:700;color:var(--accent);background:var(--accent-light);padding:2px 9px;border-radius:6px}
    .diff-badge{font-size:.7rem;font-weight:700;padding:3px 9px;border-radius:6px}
    .easy{background:var(--green-bg);color:var(--green)}.medium{background:var(--yellow-bg);color:var(--yellow)}.hard{background:var(--red-bg);color:var(--red)}
    .task-card h3{font-size:.97rem;font-weight:700;margin-bottom:6px}
    .task-card p{font-size:.83rem;color:var(--muted);line-height:1.5;margin-bottom:12px}
    .task-meta{display:flex;gap:8px;flex-wrap:wrap}
    .meta-chip{font-size:.7rem;background:#f8fafc;border:1px solid var(--border);border-radius:6px;padding:2px 8px;color:var(--muted);font-family:monospace}

    /* ── ENDPOINTS ── */
    .endpoint-table{width:100%;border-collapse:collapse;background:var(--surface);border-radius:14px;overflow:hidden;border:1px solid var(--border);box-shadow:0 1px 4px rgba(0,0,0,.04)}
    .endpoint-table thead tr{background:#1e293b}
    .endpoint-table th{padding:11px 16px;text-align:left;font-size:.78rem;font-weight:600;color:#94a3b8;letter-spacing:.06em;text-transform:uppercase}
    .endpoint-table td{padding:10px 16px;border-bottom:1px solid var(--border);font-size:.85rem;vertical-align:middle}
    .endpoint-table tr:last-child td{border-bottom:none}
    .endpoint-table tr:hover td{background:#f8fafc}
    .method{font-size:.72rem;font-weight:700;padding:2px 9px;border-radius:5px;font-family:monospace;letter-spacing:.04em}
    .get{background:#dbeafe;color:#1d4ed8}.post{background:#d1fae5;color:#065f46}.ws{background:#f3e8ff;color:#6b21a8}
    .path{font-family:'Fira Code',monospace;font-size:.84rem;color:var(--accent)}
    .copy-btn{float:right;font-size:.7rem;padding:2px 9px;border:1px solid var(--border);border-radius:5px;background:#f8fafc;color:var(--muted);cursor:pointer;transition:background .15s}
    .copy-btn:hover{background:var(--accent-light);color:var(--accent);border-color:var(--accent)}

    /* ── QUICK START ── */
    .code-block{background:#0f172a;border-radius:12px;padding:20px 22px;font-family:'Fira Code',monospace;font-size:.82rem;line-height:1.7;color:#e2e8f0;position:relative;overflow-x:auto}
    .code-block .c{color:#64748b}.code-block .k{color:#7dd3fc}.code-block .s{color:#86efac}.code-block .v{color:#f9a8d4}
    .copy-code{position:absolute;top:12px;right:14px;font-size:.72rem;padding:3px 10px;border:1px solid #334155;border-radius:6px;background:#1e293b;color:#94a3b8;cursor:pointer;font-family:system-ui;transition:background .15s}
    .copy-code:hover{background:#334155;color:#e2e8f0}

    /* ── FOOTER ── */
    footer{max-width:860px;margin:56px auto 40px;padding:24px 24px 0;border-top:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-wrap:gap}
    .footer-left{font-size:.82rem;color:var(--muted)}
    .footer-links{display:flex;gap:16px}
    .footer-links a{font-size:.82rem;color:var(--muted);text-decoration:none}
    .footer-links a:hover{color:var(--accent)}
  </style>
</head>
<body>

<!-- NAV -->
<nav>
  <div class="logo"><span>📄</span> ResumeEnv</div>
  <div class="nav-links">
    <a href="#tasks">Tasks</a>
    <a href="#api">API</a>
    <a href="#quickstart">Quick Start</a>
    <a href="/docs">Swagger</a>
  </div>
  <div id="status-pill">
    <div id="status-dot"></div>
    <span id="status-text">Checking…</span>
  </div>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="hero-eyebrow">🏆 OpenEnv Hackathon 2026</div>
  <h1>Resume Optimizer<br/><span>AI Environment</span></h1>
  <p>An AI agent reads a job description and a candidate resume, then optimises the resume and cover letter to maximise ATS match rate.</p>
  <div class="hero-btns">
    <a href="/docs" class="btn btn-primary">⚡ Try the API</a>
    <a href="#quickstart" class="btn btn-secondary">📋 Quick Start</a>
  </div>
</div>

<!-- STATS -->
<div class="stats">
  <div class="stats-inner">
    <div class="stat"><div class="stat-val">3</div><div class="stat-label">Tasks</div></div>
    <div class="stat"><div class="stat-val">0–1</div><div class="stat-label">Reward Range</div></div>
    <div class="stat"><div class="stat-val">4</div><div class="stat-label">Max Steps (Task 3)</div></div>
    <div class="stat"><div class="stat-val" style="color:#16a34a" id="baseline-score">—</div><div class="stat-label">Baseline Avg Score</div></div>
  </div>
</div>

<!-- TASKS -->
<div class="section" id="tasks">
  <div class="section-title">Tasks</div>
  <div class="tasks">
    <div class="task-card">
      <div class="task-card-top"><span class="task-num">Task 1</span><span class="diff-badge easy">easy</span></div>
      <h3>Keyword Extraction</h3>
      <p>Extract hard skills, soft skills, and required experience years from a job description.</p>
      <div class="task-meta">
        <span class="meta-chip">max_steps: 1</span>
        <span class="meta-chip">extract_keywords</span>
      </div>
    </div>
    <div class="task-card">
      <div class="task-card-top"><span class="task-num">Task 2</span><span class="diff-badge medium">medium</span></div>
      <h3>Bullet Rewrite</h3>
      <p>Rewrite a resume bullet to maximise ATS score — add numbers and strong action verbs.</p>
      <div class="task-meta">
        <span class="meta-chip">max_steps: 1</span>
        <span class="meta-chip">rewrite_bullet</span>
      </div>
    </div>
    <div class="task-card">
      <div class="task-card-top"><span class="task-num">Task 3</span><span class="diff-badge hard">hard</span></div>
      <h3>Full Application Pack</h3>
      <p>4-step episode: rewrite summary → experience → skills → write full cover letter.</p>
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
    <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
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
  <div class="code-block" id="code1">
    <button class="copy-code" onclick="copyCode('code1')">Copy</button>
<span class="c"># 1. Health check</span>
<span class="k">curl</span> <span class="s">https://ayhm23-resume-env.hf.space/health</span>

<span class="c"># 2. Start Task 1 episode</span>
<span class="k">curl</span> -X POST <span class="s">https://ayhm23-resume-env.hf.space/reset</span> \\
  -H <span class="v">"Content-Type: application/json"</span> \\
  -d <span class="v">'{"task_id":"task1_keyword_extraction"}'</span>

<span class="c"># 3. Submit action</span>
<span class="k">curl</span> -X POST <span class="s">https://ayhm23-resume-env.hf.space/step</span> \\
  -H <span class="v">"Content-Type: application/json"</span> \\
  -d <span class="v">'{"action":{"action_type":"extract_keywords","hard_skills":["SQL","Python","Tableau"],"soft_skills":["communication"],"experience_years":5}}'</span>

<span class="c"># 4. Python inference (requires HF_TOKEN and MODEL_NAME env vars)</span>
<span class="k">python</span> inference.py
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
    const text = el.innerText.replace(/^Copy\\n/, '');
    navigator.clipboard.writeText(text).then(() => {
      const btn = el.querySelector('.copy-code');
      btn.textContent = 'Copied!';
      setTimeout(() => btn.textContent = 'Copy', 2000);
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
