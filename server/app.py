# server/app.py
# FastAPI app for ResumeEnv.
# Uses openenv's create_app (exposes /reset /step /state /health /ws /web).
# Adds 3 required hackathon endpoints: /tasks /grader /baseline
#
# IMPORTANT: Pass the Environment CLASS (not an instance) to create_app.
# The framework creates a fresh instance per WebSocket session via the factory pattern.

import re
from fastapi import FastAPI, Request
from openenv.core.env_server import create_app

from models import ResumeAction, ResumeObservation
from server.resume_environment import ResumeEnvironment, PAIRS, _ats_score, _f1, _jaccard

# Pass the class (factory), not an instance — required by HTTPEnvServer
app: FastAPI = create_app(ResumeEnvironment, ResumeAction, ResumeObservation)

# Module-level tracker for last HTTP /step reward — used by /grader endpoint.
_last_step_reward: float = 0.5


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
    t1_score = round(0.60 * hard_f1 + 0.25 * soft_jac + 0.15 * exp_score, 4)
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
    t2_score = round(0.40 * ats_d + 0.30 * 0.5 + 0.30 * 1.0, 4)   # quality=1 (has number + verb)
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
    t3_score = round(0.35 * ats3 + 0.25 * cov_r + 0.25 * kw_c + 0.15 * fmt, 4)
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
