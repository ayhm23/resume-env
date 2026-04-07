#!/usr/bin/env python3
# inference.py — LLM baseline agent for ResumeEnv.
#
# Required environment variables:
#   HF_TOKEN       Your Hugging Face / API key
#   API_BASE_URL   The API endpoint for the LLM
#   MODEL_NAME     The model identifier to use
#   ENV_BASE_URL   Running ResumeEnv server (default: http://localhost:8000)
#
# Usage:
#   python inference.py

import asyncio
import sys
import json
import os
import re

from openai import OpenAI

from client import ResumeEnv
from models import ResumeAction

# ── Config from environment variables ────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.groq.com/openai/v1")
MODEL_NAME   = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
HF_TOKEN     = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
ENV_BASE_URL = os.environ.get("ENV_BASE_URL", "http://localhost:8000")


def llm(prompt: str) -> str:
    """Single LLM call using OpenAI-compatible client."""
    client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.0,
    )
    return resp.choices[0].message.content.strip()


def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON safely."""
    clean = re.sub(r"```json|```", "", raw).strip()
    return json.loads(clean)


# ─────────────────────────────────────────────────────────────────────────────
# Task 1 — Keyword Extraction
# ─────────────────────────────────────────────────────────────────────────────

BENCHMARK = "resume-env"
SUCCESS_THRESHOLD = 0.1


def log_start(task: str, model: str) -> None:
    print(f"[START] task={task} env={BENCHMARK} model={model}", flush=True)


def _clamp(v: float) -> float:
    """Clamp to (0, 1) exclusive, safe for 2-decimal formatting."""
    return max(0.01, min(0.99, float(v)))


def log_step(step: int, action: str, reward: float, done: bool, error=None) -> None:
    error_val = error if error else "null"
    print(f"[STEP] step={step} action={action} reward={_clamp(reward):.2f} done={str(done).lower()} error={error_val}", flush=True)


def log_end(steps: int, score: float, rewards: list) -> None:
    score = _clamp(score)
    success = score >= SUCCESS_THRESHOLD
    rewards_str = ",".join(f"{_clamp(r):.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


async def run_task1(seed: int = 42) -> float:
    print("\n── Task 1: Keyword Extraction ──")
    task_id = "task1_keyword_extraction"
    log_start(task=task_id, model=MODEL_NAME)
    score = 0.0
    try:
        async with ResumeEnv(base_url=ENV_BASE_URL) as env:
            result = await env.reset(task_id=task_id, seed=seed)
            obs = result.observation
            jd = obs.job_description

            prompt = f"""Read this job description and extract skills.

JD:
{jd}

Return ONLY valid JSON:
{{
  "hard_skills": ["list of tools, languages, platforms"],
  "soft_skills": ["list of soft skills"],
  "experience_years": <integer>
}}"""

            raw = llm(prompt)
            parsed = _parse_json(raw)

            action = ResumeAction(
                action_type="extract_keywords",
                hard_skills=parsed.get("hard_skills", []),
                soft_skills=parsed.get("soft_skills", []),
                experience_years=parsed.get("experience_years", 0),
            )
            step = await env.step(action)
            score = step.reward or 0.0
            log_step(step=1, action="extract_keywords", reward=score, done=True)
            print(f"  Score: {score:.4f}  |  {step.observation.feedback}")
    except Exception as exc:
        print(f"[DEBUG] task1 error: {exc}", flush=True)
        log_step(step=1, action="extract_keywords", reward=0.0, done=True, error=str(exc)[:80])
    finally:
        log_end(steps=1, score=score, rewards=[score])
    return score


# ─────────────────────────────────────────────────────────────────────────────
# Task 2 — Bullet Rewrite
# ─────────────────────────────────────────────────────────────────────────────

async def run_task2(seed: int = 42) -> float:
    print("\n── Task 2: Bullet Rewrite ──")
    task_id = "task2_bullet_rewrite"
    log_start(task=task_id, model=MODEL_NAME)

    score = 0.0
    rewritten = ""
    try:
        async with ResumeEnv(base_url=ENV_BASE_URL) as env:
            result = await env.reset(task_id=task_id, seed=seed)
            obs = result.observation
            original = obs.resume_snapshot.get("original_bullet", "")
            jd = obs.job_description

            prompt = f"""Enhance this resume bullet to better match the job description.

Job Description:
{jd}

Original bullet:
"{original}"

Rules:
- KEEP the same activity and topic from the original bullet — do not change what the person did
- Naturally weave in relevant keywords and tools from the JD
- Start with a strong past-tense action verb (Managed, Developed, Drove, Optimised, etc.)
- Include at least one specific number or percentage (e.g. "increased X by 30%")
- Keep it to 1 sentence

Return ONLY the rewritten bullet with no quotes, labels, or explanation."""

            rewritten = llm(prompt).strip('"').strip()

            action = ResumeAction(
                action_type="rewrite_bullet",
                rewritten_bullet=rewritten,
            )
            step = await env.step(action)
            score = step.reward or 0.0
            log_step(step=1, action="rewrite_bullet", reward=score, done=True)
            print(f"  Score: {score:.4f}  |  {step.observation.feedback}")
            if rewritten:
                print(f"  Rewritten: {rewritten[:100]}...")
    except Exception as exc:
        print(f"[DEBUG] task2 error: {exc}", flush=True)
        log_step(step=1, action="rewrite_bullet", reward=0.0, done=True, error=str(exc)[:80])
    finally:
        log_end(steps=1, score=score, rewards=[score])
    return score


# ─────────────────────────────────────────────────────────────────────────────
# Task 3 — Full Application Pack
# ─────────────────────────────────────────────────────────────────────────────

async def run_task3(seed: int = 42) -> float:
    print("\n── Task 3: Full Application Pack ──")
    task_id = "task3_full_application"
    STEP_SEQUENCE = [
        "rewrite_summary",
        "rewrite_experience",
        "update_skills",
        "write_cover_letter",
    ]
    log_start(task=task_id, model=MODEL_NAME)

    final_score = 0.0
    rewards_t3: list = []
    steps_done = 0
    try:
        async with ResumeEnv(base_url=ENV_BASE_URL) as env:
            result = await env.reset(task_id=task_id, seed=seed)
            obs = result.observation
            jd = obs.job_description
            resume = obs.resume_snapshot

            for step_num, step_name in enumerate(STEP_SEQUENCE, start=1):
                if step_name == "rewrite_summary":
                    prompt = (
                        f"Rewrite this professional summary to match the JD.\n"
                        f"Current: {resume.get('summary', '')}\nJD: {jd}\n"
                        f"Return ONLY the new 2-sentence summary."
                    )
                elif step_name == "rewrite_experience":
                    bullets = "\n".join(
                        b for e in resume.get("experience", []) for b in e.get("bullets", [])
                    )
                    prompt = (
                        f"Rewrite these bullets for ATS. JD keywords: {jd[:200]}\n"
                        f"Bullets:\n{bullets}\n"
                        f"Return one bullet per line, each starting with a strong verb and including a number."
                    )
                elif step_name == "update_skills":
                    prompt = (
                        f"Update skills for this JD. Current: {resume.get('skills', [])}\n"
                        f"JD: {jd[:200]}\n"
                        f"Return ONLY a comma-separated list of skills."
                    )
                elif step_name == "write_cover_letter":
                    prompt = (
                        f"Write a 3-paragraph cover letter for this role.\n"
                        f"Summary: {resume.get('summary', '')}\n"
                        f"Skills: {resume.get('skills', [])}\nJD: {jd}\n"
                        f"Start with 'Dear Hiring Manager,' and end with 'Sincerely, [Applicant]'."
                    )

                content = llm(prompt).strip()
                action = ResumeAction(action_type=step_name, content=content)
                step_result = await env.step(action)
                obs = step_result.observation
                final_score = step_result.reward or 0.0
                resume = obs.resume_snapshot
                done = obs.done
                rewards_t3.append(final_score)
                steps_done = step_num
                log_step(step=step_num, action=step_name, reward=final_score, done=done)
                print(f"  [{step_name}] reward={final_score:.4f}")

                if done:
                    break

            print(f"  Final Score: {final_score:.4f}  |  {obs.feedback}")
    except Exception as exc:
        print(f"[DEBUG] task3 error: {exc}", flush=True)
        log_step(step=steps_done + 1, action="error", reward=0.0, done=True, error=str(exc)[:80])
        if not rewards_t3:
            rewards_t3 = [0.0]
    finally:
        log_end(steps=max(len(rewards_t3), 1), score=final_score, rewards=rewards_t3 or [0.0])
    return final_score


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print(f"ResumeEnv Inference  —  model={MODEL_NAME}  server={ENV_BASE_URL}")
    print("=" * 60)

    t1 = t2 = t3 = 0.0
    try:
        t1 = await run_task1(seed=42)
        t2 = await run_task2(seed=42)
        t3 = await run_task3(seed=42)
    except Exception as exc:
        print(f"[DEBUG] Fatal error in main: {exc}", flush=True)

    overall = round((t1 + t2 + t3) / 3, 4)

    print("\n" + "=" * 60)
    print("RESULTS")
    print(f"  Task 1  Keyword Extraction   : {t1:.4f}")
    print(f"  Task 2  Bullet Rewrite       : {t2:.4f}")
    print(f"  Task 3  Full Application     : {t3:.4f}")
    print(f"  ─────────────────────────────────")
    print(f"  Overall Average              : {overall:.4f}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
    sys.exit(0)
