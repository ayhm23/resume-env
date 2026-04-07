#!/usr/bin/env python3
# inference.py  ← MUST be in project root (not a subfolder)
#
# LLM-powered baseline agent for ResumeEnv.
# Uses OpenAI-compatible client — works with OpenAI, Together, Groq, Ollama, vLLM etc.
#
# Environment variables:
#   OPENAI_API_KEY   — your API key (required)
#   API_BASE_URL     — base URL (default: https://api.openai.com/v1)
#   MODEL_NAME       — model to use  (default: gpt-4o-mini)
#   ENV_BASE_URL     — running ResumeEnv server (default: http://localhost:8000)
#
# Usage:
#   python inference.py

import asyncio
import json
import os
import re

from openai import OpenAI

from client import ResumeEnv
from models import ResumeAction

# ── Config from environment variables ────────────────────────────────────────
# HF_TOKEN is the canonical key name per hackathon requirements.
# Fall back to OPENAI_API_KEY for local dev convenience.
API_KEY      = os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME   = os.environ.get("MODEL_NAME", "gpt-4o-mini")
ENV_BASE_URL = os.environ.get("ENV_BASE_URL", "http://localhost:8000")


def llm(prompt: str) -> str:
    """Single LLM call using OpenAI-compatible client."""
    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
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

def _log(tag: str, payload: dict) -> None:
    """Emit a structured log line as required by the hackathon evaluator."""
    print(f"[{tag}] " + json.dumps(payload))


async def run_task1(seed: int = 42) -> float:
    print("\n── Task 1: Keyword Extraction ──")
    task_id = "task1_keyword_extraction"
    _log("START", {"task_id": task_id, "model": MODEL_NAME, "seed": seed})

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
        _log("STEP", {"task_id": task_id, "step": 1, "action": "extract_keywords", "reward": round(score, 4), "done": True})
        _log("END", {"task_id": task_id, "score": round(score, 4)})
        print(f"  Score: {score:.4f}  |  {step.observation.feedback}")
        return score


# ─────────────────────────────────────────────────────────────────────────────
# Task 2 — Bullet Rewrite
# ─────────────────────────────────────────────────────────────────────────────

async def run_task2(seed: int = 42) -> float:
    print("\n── Task 2: Bullet Rewrite ──")
    task_id = "task2_bullet_rewrite"
    _log("START", {"task_id": task_id, "model": MODEL_NAME, "seed": seed})

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
        _log("STEP", {"task_id": task_id, "step": 1, "action": "rewrite_bullet", "reward": round(score, 4), "done": True})
        _log("END", {"task_id": task_id, "score": round(score, 4)})
        print(f"  Score: {score:.4f}  |  {step.observation.feedback}")
        print(f"  Rewritten: {rewritten[:100]}...")
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
    _log("START", {"task_id": task_id, "model": MODEL_NAME, "seed": seed})

    async with ResumeEnv(base_url=ENV_BASE_URL) as env:
        result = await env.reset(task_id=task_id, seed=seed)
        obs = result.observation
        jd = obs.job_description
        resume = obs.resume_snapshot
        final_score = 0.0

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
            _log("STEP", {"task_id": task_id, "step": step_num, "action": step_name, "reward": round(final_score, 4), "done": done})
            print(f"  [{step_name}] reward={final_score:.4f}")

            if done:
                break

        _log("END", {"task_id": task_id, "score": round(final_score, 4)})
        print(f"  Final Score: {final_score:.4f}  |  {obs.feedback}")
        return final_score


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print(f"ResumeEnv Inference  —  model={MODEL_NAME}  server={ENV_BASE_URL}")
    print("=" * 60)

    t1 = await run_task1(seed=42)
    t2 = await run_task2(seed=42)
    t3 = await run_task3(seed=42)

    overall = round((t1 + t2 + t3) / 3, 4)

    _log("END", {"task_id": "all", "task1": round(t1, 4), "task2": round(t2, 4), "task3": round(t3, 4), "overall": overall})

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
