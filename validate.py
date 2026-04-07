#!/usr/bin/env python3
"""
validate.py — ResumeEnv Pre-Submission Validator
=================================================
Run this BEFORE submitting your HF Spaces URL.
Checks every criterion from the hackathon's automated disqualification list.

Usage:
    # Against local server (start it first):
    python validate.py --base-url http://localhost:8000

    # Against deployed HF Space:
    python validate.py --base-url https://your-username-resume-env.hf.space

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

import argparse
import asyncio
import json
import sys
import time
import httpx


PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"

results = []


def check(name: str, passed: bool, detail: str = ""):
    icon = PASS if passed else FAIL
    msg = f"  {icon}  {name}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((name, passed, detail))
    return passed


# ─────────────────────────────────────────────────────────────────────────────
# 1. Health check — space must return 200
# ─────────────────────────────────────────────────────────────────────────────

def test_health(base_url: str):
    print("\n[1] Health Check")
    try:
        r = httpx.get(f"{base_url}/health", timeout=15)
        check("GET /health returns 200", r.status_code == 200, f"status={r.status_code}")
        data = r.json()
        check("/health body contains 'status'", "status" in data, str(data))
    except Exception as e:
        check("GET /health reachable", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 2. reset() — must accept task_id and return observation
# ─────────────────────────────────────────────────────────────────────────────

def test_reset(base_url: str):
    print("\n[2] reset() API")
    for task_id in [
        "task1_keyword_extraction",
        "task2_bullet_rewrite",
        "task3_full_application",
    ]:
        try:
            r = httpx.post(
                f"{base_url}/reset",
                json={"task_id": task_id},
                timeout=15,
            )
            ok = r.status_code == 200
            check(f"POST /reset task_id={task_id}", ok, f"status={r.status_code}")
            if ok:
                data = r.json()
                obs = data.get("observation", data)
                has_jd = bool(obs.get("job_description", ""))
                check(f"  observation.job_description present", has_jd)
        except Exception as e:
            check(f"POST /reset task_id={task_id}", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 3. step() — must accept actions and return reward + done
# ─────────────────────────────────────────────────────────────────────────────

def test_step(base_url: str):
    print("\n[3] step() API")

    # Task 1
    try:
        httpx.post(f"{base_url}/reset", json={"task_id": "task1_keyword_extraction"}, timeout=15)
        r = httpx.post(
            f"{base_url}/step",
            json={"action": {
                "action_type": "extract_keywords",
                "hard_skills": ["SQL", "Python"],
                "soft_skills": ["communication"],
                "experience_years": 3,
                "rewritten_bullet": "",
                "content": "",
            }},
            timeout=15,
        )
        ok = r.status_code == 200
        check("POST /step task1 returns 200", ok, f"status={r.status_code}")
        if ok:
            data = r.json()
            check("  reward in [0.0, 1.0]", 0.0 <= (data.get("reward") or 0.0) <= 1.0,
                  f"reward={data.get('reward')}")
            check("  done is bool", isinstance(data.get("done"), bool))
    except Exception as e:
        check("POST /step task1", False, str(e))

    # Task 2
    try:
        httpx.post(f"{base_url}/reset", json={"task_id": "task2_bullet_rewrite"}, timeout=15)
        r = httpx.post(
            f"{base_url}/step",
            json={"action": {
                "action_type": "rewrite_bullet",
                "hard_skills": [],
                "soft_skills": [],
                "experience_years": 0,
                "rewritten_bullet": "Developed SQL dashboards tracking 15 KPIs, reducing reporting time by 30%.",
                "content": "",
            }},
            timeout=15,
        )
        ok = r.status_code == 200
        check("POST /step task2 returns 200", ok, f"status={r.status_code}")
        if ok:
            data = r.json()
            check("  reward in [0.0, 1.0]", 0.0 <= (data.get("reward") or 0.0) <= 1.0,
                  f"reward={data.get('reward')}")
    except Exception as e:
        check("POST /step task2", False, str(e))

    # Task 3 — run all 4 steps
    try:
        httpx.post(f"{base_url}/reset", json={"task_id": "task3_full_application"}, timeout=15)
        steps = [
            ("rewrite_summary",    "Experienced analyst with 5 years driving data-informed decisions."),
            ("rewrite_experience", "Developed SQL dashboards tracking 15 KPIs, reducing reporting time by 30%."),
            ("update_skills",      "SQL, Python, Tableau, BigQuery, dbt, stakeholder communication"),
            ("write_cover_letter", "Dear Hiring Manager,\n\nI am excited to apply.\n\nSincerely, Applicant"),
        ]
        last_reward = 0.0
        for action_type, content in steps:
            r = httpx.post(
                f"{base_url}/step",
                json={"action": {
                    "action_type": action_type,
                    "hard_skills": [], "soft_skills": [],
                    "experience_years": 0,
                    "rewritten_bullet": "",
                    "content": content,
                }},
                timeout=15,
            )
            ok = r.status_code == 200
            if ok:
                data = r.json()
                last_reward = data.get("reward") or 0.0
        check("POST /step task3 full 4-step episode", ok, f"final reward={last_reward:.4f}")
        check("  final reward in [0.0, 1.0]", 0.0 <= last_reward <= 1.0)
    except Exception as e:
        check("POST /step task3", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 4. state() — must return episode metadata
# ─────────────────────────────────────────────────────────────────────────────

def test_state(base_url: str):
    print("\n[4] state() API")
    try:
        httpx.post(f"{base_url}/reset", json={"task_id": "task1_keyword_extraction"}, timeout=15)
        r = httpx.get(f"{base_url}/state", timeout=15)
        ok = r.status_code == 200
        check("GET /state returns 200", ok)
        if ok:
            data = r.json()
            check("  state has step_count", "step_count" in data, str(list(data.keys())))
            check("  state has episode_id", "episode_id" in data)
    except Exception as e:
        check("GET /state", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 5. /tasks — list with 3 tasks and action schemas
# ─────────────────────────────────────────────────────────────────────────────

def test_tasks(base_url: str):
    print("\n[5] /tasks Endpoint")
    try:
        r = httpx.get(f"{base_url}/tasks", timeout=15)
        ok = r.status_code == 200
        check("GET /tasks returns 200", ok)
        if ok:
            data = r.json()
            tasks = data.get("tasks", [])
            check("  at least 3 tasks returned", len(tasks) >= 3, f"got {len(tasks)}")
            diffs = {t.get("difficulty") for t in tasks}
            check("  easy + medium + hard all present", {"easy", "medium", "hard"} <= diffs,
                  f"found: {diffs}")
            for t in tasks:
                has_schema = bool(t.get("action_schema"))
                check(f"  task '{t.get('id')}' has action_schema", has_schema)
    except Exception as e:
        check("GET /tasks", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 6. /grader — returns score after completed episode
# ─────────────────────────────────────────────────────────────────────────────

def test_grader(base_url: str):
    print("\n[6] /grader Endpoint")
    try:
        # Complete an episode first
        httpx.post(f"{base_url}/reset", json={"task_id": "task1_keyword_extraction"}, timeout=15)
        httpx.post(
            f"{base_url}/step",
            json={"action": {
                "action_type": "extract_keywords",
                "hard_skills": ["SQL", "Python", "Tableau"],
                "soft_skills": ["communication"],
                "experience_years": 5,
                "rewritten_bullet": "", "content": "",
            }},
            timeout=15,
        )
        r = httpx.get(f"{base_url}/grader", timeout=15)
        ok = r.status_code == 200
        check("GET /grader returns 200", ok)
        if ok:
            data = r.json()
            score = data.get("final_score", data.get("grader_result", {}).get("final_score"))
            check("  final_score present and in [0.0, 1.0]",
                  score is not None and 0.0 <= float(score) <= 1.0,
                  f"final_score={score}")
    except Exception as e:
        check("GET /grader", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 7. /baseline — runs without error, returns 3 task scores
# ─────────────────────────────────────────────────────────────────────────────

def test_baseline(base_url: str):
    print("\n[7] /baseline Endpoint")
    try:
        r = httpx.post(f"{base_url}/baseline", timeout=60)
        ok = r.status_code == 200
        check("POST /baseline returns 200", ok, f"status={r.status_code}")
        if ok:
            data = r.json()
            results_data = data.get("results", {})
            check("  task1 score present", "task1_keyword_extraction" in results_data)
            check("  task2 score present", "task2_bullet_rewrite" in results_data)
            check("  task3 score present", "task3_full_application" in results_data)
            overall = data.get("overall_average_score", 0.0)
            check("  overall_average_score in [0.0, 1.0]",
                  0.0 <= overall <= 1.0, f"overall={overall}")
            for task, r_data in results_data.items():
                score = r_data.get("score", -1)
                check(f"  {task} score in [0.0, 1.0]",
                      0.0 <= score <= 1.0, f"score={score}")
    except Exception as e:
        check("POST /baseline", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 8. Grader scores in range [0.0, 1.0] for all tasks
# ─────────────────────────────────────────────────────────────────────────────

def test_grader_ranges(base_url: str):
    print("\n[8] Grader Score Ranges (all tasks)")
    task_actions = {
        "task1_keyword_extraction": {
            "action_type": "extract_keywords",
            "hard_skills": ["SQL", "Python", "Tableau", "BigQuery"],
            "soft_skills": ["stakeholder communication"],
            "experience_years": 5,
            "rewritten_bullet": "", "content": "",
        },
        "task2_bullet_rewrite": {
            "action_type": "rewrite_bullet",
            "hard_skills": [], "soft_skills": [], "experience_years": 0,
            "rewritten_bullet": "Developed Python dashboards tracking 20 KPIs, reducing manual reporting by 45%.",
            "content": "",
        },
    }
    for task_id, action in task_actions.items():
        try:
            httpx.post(f"{base_url}/reset", json={"task_id": task_id}, timeout=15)
            r = httpx.post(f"{base_url}/step", json={"action": action}, timeout=15)
            data = r.json()
            reward = data.get("reward", -1)
            check(f"  {task_id} reward in [0.0, 1.0]",
                  0.0 <= reward <= 1.0, f"reward={reward}")
        except Exception as e:
            check(f"  {task_id} grader", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 9. openenv.yaml present and valid
# ─────────────────────────────────────────────────────────────────────────────

def test_yaml():
    print("\n[9] openenv.yaml")
    import os
    try:
        path = os.path.join(os.path.dirname(__file__), "openenv.yaml")
        exists = os.path.exists(path)
        check("openenv.yaml exists at project root", exists)
        if exists:
            with open(path) as f:
                content = f.read()
            check("  contains 'name'",    "name:" in content)
            check("  contains 'version'", "version:" in content)
            check("  contains 'sdk'",     "sdk:" in content)
    except Exception as e:
        check("openenv.yaml readable", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 10. Dockerfile present
# ─────────────────────────────────────────────────────────────────────────────

def test_dockerfile():
    print("\n[10] Dockerfile")
    import os
    path = os.path.join(os.path.dirname(__file__), "server", "Dockerfile")
    exists = os.path.exists(path)
    check("server/Dockerfile exists", exists)
    if exists:
        with open(path) as f:
            content = f.read()
        check("  contains FROM (base image)", "FROM " in content)
        check("  contains EXPOSE 8000", "EXPOSE 8000" in content)
        check("  contains CMD or ENTRYPOINT", "CMD " in content or "ENTRYPOINT " in content)


# ─────────────────────────────────────────────────────────────────────────────
# 11. inference.py is in project root
# ─────────────────────────────────────────────────────────────────────────────

def test_inference_location():
    print("\n[11] inference.py")
    import os
    path = os.path.join(os.path.dirname(__file__), "inference.py")
    exists = os.path.exists(path)
    check("inference.py exists at PROJECT ROOT (not a subfolder)", exists)
    if exists:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        check("  uses HF_TOKEN or OPENAI_API_KEY",
              "HF_TOKEN" in content or "OPENAI_API_KEY" in content)
        check("  uses MODEL_NAME",     "MODEL_NAME" in content)
        check("  uses API_BASE_URL",   "API_BASE_URL" in content)


# ─────────────────────────────────────────────────────────────────────────────
# 12. No heavy ML deps in server/requirements.txt
# ─────────────────────────────────────────────────────────────────────────────

def test_deps():
    print("\n[12] Dependency Safety")
    import os
    path = os.path.join(os.path.dirname(__file__), "server", "requirements.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            content = f.read().lower()
        BANNED = ["sentence-transformers", "torch", "tensorflow", "transformers",
                  "spacy", "nltk", "gensim", "sklearn", "scikit-learn"]
        for dep in BANNED:
            check(f"  server/requirements.txt does NOT contain '{dep}'",
                  dep not in content, f"Found: {dep}")
    else:
        check("server/requirements.txt exists", False)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ResumeEnv Pre-Submission Validator")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="Base URL of running ResumeEnv server")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    print("=" * 60)
    print(f"ResumeEnv Validator — {base}")
    print("=" * 60)

    # Static checks (no server needed)
    test_yaml()
    test_dockerfile()
    test_inference_location()
    test_deps()

    # Live server checks
    test_health(base)
    test_reset(base)
    test_step(base)
    test_state(base)
    test_tasks(base)
    test_grader(base)
    test_baseline(base)
    test_grader_ranges(base)

    # Summary
    passed = sum(1 for _, p, _ in results if p)
    total  = len(results)
    failed = [(n, d) for n, p, d in results if not p]

    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/{total} checks passed")

    if failed:
        print(f"\n{FAIL} Failed checks:")
        for name, detail in failed:
            print(f"  • {name}")
            if detail:
                print(f"    {detail}")
        print("\n⚠️  Fix all failures before submitting.")
        sys.exit(1)
    else:
        print("\n🎉 All checks passed! Safe to submit your HF Spaces URL.")
        sys.exit(0)


if __name__ == "__main__":
    main()
