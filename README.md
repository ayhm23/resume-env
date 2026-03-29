---
title: resume-env
emoji: 📄
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8000
tags:
  - openenv
  - rl-environment
  - resume
  - ats
  - job-application
license: mit
---

# ResumeEnv 🎯
**Job Application Optimizer — OpenEnv Environment**

An OpenEnv-compliant environment where an AI agent reads a job description and a candidate resume, then optimizes the resume and cover letter to maximize ATS (Applicant Tracking System) match rate.

---

## Install & Run

```bash
# Install client
pip install git+https://huggingface.co/spaces/your-username/resume-env

# Run locally with Docker
docker build -t resume-env .
docker run -p 8000:8000 resume-env
```

## Quick Start

```python
import asyncio
from resume_env import ResumeEnv, ResumeAction

async def main():
    async with ResumeEnv(base_url="https://your-username-resume-env.hf.space") as env:

        # Task 1 — Keyword Extraction
        result = await env.reset(task_id="task1_keyword_extraction")
        print(result.observation.job_description)

        result = await env.step(ResumeAction(
            action_type="extract_keywords",
            hard_skills=["SQL", "Python", "Tableau"],
            soft_skills=["stakeholder communication"],
            experience_years=5,
        ))
        print(f"Score: {result.reward}")  # e.g. 0.78

asyncio.run(main())

# Sync usage
from resume_env import ResumeEnv, ResumeAction
with ResumeEnv(base_url="http://localhost:8000").sync() as env:
    result = env.reset(task_id="task2_bullet_rewrite")
    result = env.step(ResumeAction(
        action_type="rewrite_bullet",
        rewritten_bullet="Developed Tableau dashboards tracking 12 KPIs...",
    ))
    print(result.reward)
```

---

## API Endpoints

| Endpoint    | Method | Description |
|-------------|--------|-------------|
| `/reset`    | POST   | Start new episode. Body: `{"task_id": "task1_keyword_extraction"}` |
| `/step`     | POST   | Submit action, get observation + reward |
| `/state`    | GET    | Episode metadata (step_count, episode_id, cumulative_reward) |
| `/tasks`    | GET    | List all tasks with action schemas |
| `/grader`   | GET    | Last episode grader scores |
| `/baseline` | POST   | Run rule-based baseline on all 3 tasks |
| `/health`   | GET    | `{"status": "ok"}` |
| `/ws`       | WS     | WebSocket (used by Python client) |
| `/web`      | GET    | Interactive browser UI |

---

## Tasks

### Task 1 — Keyword Extraction (Easy) · max_steps=1

**Goal:** Extract structured skills from a job description.

**Action:**
```json
{
  "action_type": "extract_keywords",
  "hard_skills": ["SQL", "Python", "Tableau"],
  "soft_skills": ["stakeholder communication"],
  "experience_years": 5
}
```

**Reward:** `0.60 × hard_skill_F1 + 0.25 × soft_skill_Jaccard + 0.15 × experience_accuracy`

---

### Task 2 — Bullet Rewrite (Medium) · max_steps=1

**Goal:** Rewrite one resume bullet for maximum ATS match.

**Action:**
```json
{
  "action_type": "rewrite_bullet",
  "rewritten_bullet": "Developed Tableau dashboards tracking 12 KPIs, reducing reporting time by 40%."
}
```

**Reward:** `0.40 × ATS_improvement + 0.30 × semantic_preservation + 0.30 × quality`

Quality = strong action verb (0.5) + quantification present (0.5).

---

### Task 3 — Full Application Pack (Hard) · max_steps=4

**Goal:** Build a complete tailored application in 4 sequential steps.

| Step | action_type | content |
|------|-------------|---------|
| 1 | `rewrite_summary` | New 2-sentence professional summary |
| 2 | `rewrite_experience` | Rewritten bullets, one per line |
| 3 | `update_skills` | Comma-separated updated skills list |
| 4 | `write_cover_letter` | Full cover letter starting with "Dear Hiring Manager," |

**Final Reward:** `0.35 × resume_ATS + 0.25 × cover_relevance + 0.25 × keyword_coverage + 0.15 × format_score`

Partial rewards are given after each step.

---

## Observation Space

Every observation (`ResumeObservation`) contains:

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | str | Current task |
| `job_description` | str | Full JD text |
| `resume_snapshot` | dict | Current resume state |
| `feedback` | str | Human-readable score breakdown |
| `current_score` | float | Score so far |
| `steps_remaining` | int | Steps left in episode |
| `done` | bool | Episode complete |
| `reward` | float | Step reward |
| `metadata` | dict | Detailed grader breakdown |

---

## Baseline

```bash
# Rule-based (no LLM, always works)
curl -X POST http://localhost:8000/baseline

# LLM baseline
export OPENAI_API_KEY=sk-...
export MODEL_NAME=gpt-4o-mini
python inference.py
```

Expected baseline scores:

| Task | Rule-based | LLM (gpt-4o-mini) |
|------|-----------|-------------------|
| Task 1 | ~0.48 | ~0.80 |
| Task 2 | ~0.55 | ~0.72 |
| Task 3 | ~0.38 | ~0.65 |

---

## Project Structure

```
resume_env/
├── __init__.py               ← exports ResumeAction, ResumeObservation, ResumeState, ResumeEnv
├── models.py                 ← Action / Observation / State dataclasses
├── client.py                 ← ResumeEnv(HTTPEnvClient)
├── inference.py              ← LLM baseline agent (OpenAI-compatible)
├── openenv.yaml              ← OpenEnv manifest
├── pyproject.toml
├── .dockerignore
├── README.md
└── server/
    ├── __init__.py
    ├── resume_environment.py ← ResumeEnvironment (reset / step / state)
    ├── app.py                ← FastAPI (create_web_interface_app + /tasks /grader /baseline)
    ├── requirements.txt      ← server deps (no ML libraries)
    └── Dockerfile
```

---

## Deploy

```bash
cd resume_env
openenv push --repo-id your-username/resume-env
```

---

## License
BSD-3-Clause
