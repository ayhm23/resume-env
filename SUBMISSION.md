# ResumeEnv — Submission Guide
**Deadline: 7 April 2026, 11:59 PM IST**

Follow every step in order. Do not skip.

---

## Step 0 — Prerequisites (do before April 1st)

```bash
# Python 3.10+
python --version

# pip install tools
pip install openenv-core huggingface_hub

# HF login
huggingface-cli login   # paste your HF token

# Docker (needed for local testing)
docker --version
```

---

## Step 1 — Install & verify locally (no Docker yet)

```bash
cd resume_env

# Install in editable mode
pip install -e .

# Start server directly (fastest for dev)
uvicorn server.app:app --reload --port 8000

# In a second terminal — quick smoke test:
curl http://localhost:8000/health
curl http://localhost:8000/tasks
curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" \
     -d '{"task_id": "task1_keyword_extraction"}'
```

You should see:
- `/health` → `{"status": "ok"}`
- `/tasks` → JSON with 3 tasks
- `/reset` → observation with `job_description`

---

## Step 2 — Test all 3 tasks manually

```bash
# Task 1 — full episode
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "task1_keyword_extraction"}'

curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "extract_keywords",
    "hard_skills": ["SQL", "Python", "Tableau", "BigQuery"],
    "soft_skills": ["stakeholder communication"],
    "experience_years": 5,
    "rewritten_bullet": "",
    "content": ""
  }'

curl http://localhost:8000/grader

# Task 2 — full episode
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "task2_bullet_rewrite"}'

curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "rewrite_bullet",
    "hard_skills": [], "soft_skills": [], "experience_years": 0,
    "rewritten_bullet": "Developed Tableau dashboards tracking 12 KPIs for C-suite reporting, reducing reporting time by 40% using SQL and Python.",
    "content": ""
  }'

# Baseline (no LLM needed)
curl -X POST http://localhost:8000/baseline
```

All rewards must be in [0.0, 1.0]. If anything is wrong, fix before Docker.

---

## Step 3 — Run the pre-submission validator

```bash
# Server must be running on :8000
python validate.py --base-url http://localhost:8000
```

**All 12 check groups must show ✅ PASS before you continue.**

Common failures and fixes:
| Failure | Fix |
|---------|-----|
| `/health` not reachable | Is the server running? |
| reward not in [0.0, 1.0] | Check `_step_t1/t2/t3` return values |
| /grader returns error | Run reset+step first |
| inference.py not at root | It's already there — don't move it |
| ML dep found in requirements | It's clean — don't add any |

---

## Step 4 — Docker build and test

```bash
# Build
docker build -f server/Dockerfile -t resume-env .

# Run
docker run -p 8000:8000 resume-env

# Validate against Docker container
python validate.py --base-url http://localhost:8000
```

If Docker build fails:
- Check `server/requirements.txt` — all packages must exist on PyPI
- Check `server/Dockerfile` COPY paths match actual file locations

---

## Step 5 — Run inference.py (LLM baseline)

```bash
# Set your API key
export OPENAI_API_KEY=sk-...
export MODEL_NAME=gpt-4o-mini    # or gpt-4o, or any OpenAI-compatible model

# Server must be running
python inference.py
```

Expected output (approximate):
```
Task 1  Keyword Extraction   : 0.7800
Task 2  Bullet Rewrite       : 0.6900
Task 3  Full Application     : 0.6200
Overall Average              : 0.6967
```

**The script must complete without error.** If it fails:
- Check `OPENAI_API_KEY` is set
- Check server is running at `ENV_BASE_URL` (default: http://localhost:8000)
- The LLM responses must be parseable JSON for Task 1

---

## Step 6 — Deploy to HF Spaces

```bash
cd resume_env

# Deploy (will create a new Space or update existing)
openenv push --repo-id YOUR_HF_USERNAME/resume-env
```

Wait for the build to complete (~2-3 mins). Check the build logs in the HF Space UI.

**Your Space URL will be:**
`https://YOUR_HF_USERNAME-resume-env.hf.space`

---

## Step 7 — Final validation against HF Space

```bash
# Wait until Space is fully awake (first request can take 30-60s)
python validate.py --base-url https://YOUR_HF_USERNAME-resume-env.hf.space
```

All 12 checks must pass. The automated hackathon checker runs the same logic.

---

## Step 8 — Submit

Go to the hackathon dashboard and paste:
```
https://YOUR_HF_USERNAME-resume-env.hf.space
```

**Check before submitting:**
- [ ] `/health` returns 200
- [ ] `/reset` responds to all 3 task_ids
- [ ] `/step` returns reward in [0.0, 1.0] for all tasks
- [ ] `/tasks` lists 3 tasks (easy, medium, hard) with action schemas
- [ ] `/grader` returns final_score after completed episode
- [ ] `/baseline` completes without error and returns 3 scores
- [ ] `inference.py` runs without error
- [ ] Docker image builds cleanly
- [ ] `validate.py` passes all 12 checks

---

## Troubleshooting

**"Space is sleeping"** — HF free tier Spaces sleep after inactivity.
First request takes 30-60s. The validator handles this but if it times out,
curl the /health endpoint manually first to wake it up.

**"reset returns 422"** — wrong JSON body. Must include `task_id` key.

**"step returns 422"** — include ALL action fields even if unused:
```json
{
  "action_type": "...",
  "hard_skills": [], "soft_skills": [], "experience_years": 0,
  "rewritten_bullet": "", "content": ""
}
```

**"Docker build fails with 'openenv-base not found'"** — The real base image tag
may differ. Check: `docker pull ghcr.io/meta-pytorch/openenv-base:latest`
If unavailable, replace with `python:3.11-slim` and add openenv-core to requirements.

---

## Key Commands Reference

```bash
# Dev server (fastest iteration)
uvicorn server.app:app --reload --port 8000

# Docker build + run
docker build -f server/Dockerfile -t resume-env . && docker run -p 8000:8000 resume-env

# Validate
python validate.py --base-url http://localhost:8000

# Deploy
openenv push --repo-id USERNAME/resume-env

# Run inference
OPENAI_API_KEY=sk-... python inference.py
```
