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
  <title>ResumeEnv</title>
  <style>
    body{font-family:system-ui,sans-serif;max-width:820px;margin:40px auto;padding:0 20px;background:#f8fafc;color:#1e293b}
    h1{font-size:2rem;margin-bottom:4px}
    .badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:.75rem;font-weight:600;margin-left:8px}
    .v{background:#d1fae5;color:#065f46}.s{background:#dbeafe;color:#1e40af}
    p{color:#475569;margin:6px 0 20px}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin:24px 0}
    .card{background:#fff;border-radius:10px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
    .card h3{margin:0 0 6px;font-size:1rem}
    .card p{margin:0;font-size:.85rem;color:#64748b}
    .diff{font-size:.7rem;font-weight:700;padding:2px 8px;border-radius:8px;float:right;margin-top:-2px}
    .easy{background:#d1fae5;color:#065f46}.medium{background:#fef9c3;color:#854d0e}.hard{background:#fee2e2;color:#991b1b}
    table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}
    th{background:#1e293b;color:#fff;padding:10px 14px;text-align:left;font-size:.8rem}
    td{padding:9px 14px;border-bottom:1px solid #f1f5f9;font-size:.85rem;font-family:monospace}
    tr:last-child td{border-bottom:none}
    .tag{display:inline-block;padding:1px 7px;border-radius:6px;font-size:.75rem;background:#e0f2fe;color:#0369a1;font-family:system-ui}
    a{color:#2563eb;text-decoration:none}a:hover{text-decoration:underline}
    .footer{margin-top:40px;font-size:.8rem;color:#94a3b8;text-align:center}
  </style>
</head>
<body>
  <h1>ResumeEnv <span class="badge v">v1.0.0</span><span class="badge s">OpenEnv</span></h1>
  <p>AI agent environment — optimise resumes &amp; cover letters to maximise ATS match rate across 3 tasks.</p>

  <div class="grid">
    <div class="card">
      <h3>Task 1 <span class="diff easy">easy</span></h3>
      <p><strong>Keyword Extraction</strong><br/>Extract hard skills, soft skills &amp; experience years from a job description.</p>
    </div>
    <div class="card">
      <h3>Task 2 <span class="diff medium">medium</span></h3>
      <p><strong>Bullet Rewrite</strong><br/>Rewrite a resume bullet to maximise ATS score with numbers &amp; action verbs.</p>
    </div>
    <div class="card">
      <h3>Task 3 <span class="diff hard">hard</span></h3>
      <p><strong>Full Application Pack</strong><br/>4-step episode: rewrite summary → experience → skills → cover letter.</p>
    </div>
  </div>

  <h2 style="margin-bottom:12px">API Endpoints</h2>
  <table>
    <tr><th>Method</th><th>Path</th><th>Description</th></tr>
    <tr><td><span class="tag">GET</span></td><td>/health</td><td>Liveness check</td></tr>
    <tr><td><span class="tag">GET</span></td><td>/tasks</td><td>List all tasks &amp; action schemas</td></tr>
    <tr><td><span class="tag">POST</span></td><td>/reset</td><td>Start a new episode — body: <code>{"task_id": "..."}</code></td></tr>
    <tr><td><span class="tag">POST</span></td><td>/step</td><td>Submit an action, receive reward &amp; observation</td></tr>
    <tr><td><span class="tag">GET</span></td><td>/state</td><td>Current episode state</td></tr>
    <tr><td><span class="tag">GET</span></td><td>/grader</td><td>Last episode grader scores</td></tr>
    <tr><td><span class="tag">POST</span></td><td>/baseline</td><td>Run deterministic rule-based baseline</td></tr>
    <tr><td><span class="tag">GET</span></td><td>/docs</td><td>Interactive Swagger UI</td></tr>
  </table>

  <div class="footer">
    ResumeEnv &mdash; <a href="/docs">Swagger docs</a> &mdash; <a href="/health">Health</a> &mdash; <a href="/tasks">Tasks</a>
  </div>
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
