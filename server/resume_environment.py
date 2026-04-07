# server/resume_environment.py
# Core ResumeEnvironment — subclasses openenv.core.env_server.Environment
# All grading logic is embedded here: pure regex + keyword sets, zero ML deps.

import re
import uuid
import random
import hashlib
from typing import List, Dict, Any

from openenv.core.env_server import Environment
from models import ResumeAction, ResumeObservation, ResumeState


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC DATASET — 10 (resume, JD) pairs embedded directly.
# No file I/O, no data/ subfolder needed. Docker-safe.
# ─────────────────────────────────────────────────────────────────────────────

PAIRS = [
    {
        "id": "p01",
        "resume": {
            "name": "Priya Sharma",
            "summary": "Analyst with 4 years of experience in data and reporting.",
            "experience": [
                {"title": "Data Analyst", "company": "RetailCo", "bullets": [
                    "Helped the team build dashboards for business reporting.",
                    "Worked with SQL to pull data from internal databases.",
                ]},
            ],
            "skills": ["SQL", "Excel", "Python", "Tableau"],
        },
        "jd": (
            "Seeking a Senior Data Analyst with 5+ years using SQL, Python, Tableau, "
            "and BigQuery. Must have KPI tracking, stakeholder communication, and dbt experience. "
            "PMP certification preferred."
        ),
        "gt_hard": ["SQL", "Python", "Tableau", "BigQuery", "dbt"],
        "gt_soft": ["stakeholder communication", "data storytelling"],
        "gt_years": 5,
    },
    {
        "id": "p02",
        "resume": {
            "name": "Arjun Mehta",
            "summary": "Backend engineer with 3 years of Python and Django experience.",
            "experience": [
                {"title": "Backend Engineer", "company": "FinTechCo", "bullets": [
                    "Built REST APIs using Python and Django.",
                    "Worked on database performance improvements.",
                ]},
            ],
            "skills": ["Python", "Django", "PostgreSQL", "Git"],
        },
        "jd": (
            "Hiring a Senior Software Engineer for microservices using FastAPI, Kubernetes, "
            "and AWS. Docker, PostgreSQL, Redis, CI/CD pipelines required. 7+ years experience. "
            "System design and mentoring skills needed."
        ),
        "gt_hard": ["FastAPI", "Kubernetes", "AWS", "Docker", "PostgreSQL", "Redis", "CI/CD"],
        "gt_soft": ["system design", "mentoring"],
        "gt_years": 7,
    },
    {
        "id": "p03",
        "resume": {
            "name": "Sara Johnson",
            "summary": "Marketing professional focused on content and social media.",
            "experience": [
                {"title": "Marketing Associate", "company": "BrandAgency", "bullets": [
                    "Managed social media accounts across platforms.",
                    "Tracked campaign performance in Google Analytics.",
                ]},
            ],
            "skills": ["Social Media", "Content Writing", "Google Analytics", "Canva"],
        },
        "jd": (
            "Looking for a Growth Marketing Manager with SEO, SEM, Google Ads, Meta Ads, "
            "HubSpot, A/B testing, and CRO expertise. Salesforce CRM experience a plus. 4+ years."
        ),
        "gt_hard": ["SEO", "SEM", "Google Ads", "Meta Ads", "HubSpot", "A/B testing", "CRO"],
        "gt_soft": ["analytical mindset", "growth mindset"],
        "gt_years": 4,
    },
    {
        "id": "p04",
        "resume": {
            "name": "Wei Zhang",
            "summary": "ML engineer with 3 years building production models.",
            "experience": [
                {"title": "ML Engineer", "company": "AdTech", "bullets": [
                    "Trained classification models for ad targeting.",
                    "Deployed models using Flask on AWS EC2.",
                ]},
            ],
            "skills": ["Python", "TensorFlow", "scikit-learn", "AWS"],
        },
        "jd": (
            "Seeking Senior ML Engineer for recommendation systems. Must have PyTorch, MLflow, "
            "Kubernetes, Feast feature store, Spark pipelines, and LLM fine-tuning (LoRA, PEFT). "
            "5+ years experience."
        ),
        "gt_hard": ["PyTorch", "MLflow", "Kubernetes", "Feast", "Spark", "LoRA", "PEFT"],
        "gt_soft": ["experiment design", "cross-functional leadership"],
        "gt_years": 5,
    },
    {
        "id": "p05",
        "resume": {
            "name": "Rohan Gupta",
            "summary": "Finance analyst with 3 years in FP&A and financial modelling.",
            "experience": [
                {"title": "Financial Analyst", "company": "MidCap Ltd", "bullets": [
                    "Built monthly financial models in Excel.",
                    "Prepared budget vs actuals reports for management.",
                ]},
            ],
            "skills": ["Excel", "PowerPoint", "SAP", "SQL"],
        },
        "jd": (
            "Seeking Senior Finance Manager, FP&A. Must have Anaplan, Power BI, DCF modelling, "
            "M&A experience, SQL. CFA or CPA preferred. 6+ years in FP&A."
        ),
        "gt_hard": ["Anaplan", "Power BI", "DCF", "SQL", "M&A modelling"],
        "gt_soft": ["strategic thinking", "executive communication"],
        "gt_years": 6,
    },
    {
        "id": "p06",
        "resume": {
            "name": "Daniel Okafor",
            "summary": "Frontend developer with 4 years building React apps.",
            "experience": [
                {"title": "Frontend Developer", "company": "SaaSco", "bullets": [
                    "Built UIs using React and Redux.",
                    "Wrote unit tests with Jest.",
                ]},
            ],
            "skills": ["React", "JavaScript", "CSS", "Jest", "Git"],
        },
        "jd": (
            "Hiring Senior Frontend Engineer. Expert in React, TypeScript, Next.js, GraphQL, "
            "Storybook, Cypress. Web performance optimization, WCAG 2.1 accessibility. 5+ years."
        ),
        "gt_hard": ["TypeScript", "Next.js", "GraphQL", "Storybook", "Cypress", "WCAG"],
        "gt_soft": ["attention to detail", "accessibility mindset"],
        "gt_years": 5,
    },
    {
        "id": "p07",
        "resume": {
            "name": "Kavya Nair",
            "summary": "DevOps engineer with 3 years managing CI/CD pipelines.",
            "experience": [
                {"title": "DevOps Engineer", "company": "CloudCo", "bullets": [
                    "Managed Jenkins pipelines for 10 microservices.",
                    "Set up monitoring using Prometheus and Grafana.",
                ]},
            ],
            "skills": ["Jenkins", "AWS", "Prometheus", "Terraform", "Bash"],
        },
        "jd": (
            "Platform Engineer / SRE role. Kubernetes EKS, Terraform, ArgoCD GitOps, "
            "OpenTelemetry, Datadog, PagerDuty incident management, Python and Go required. "
            "AWS Solutions Architect cert preferred."
        ),
        "gt_hard": ["Kubernetes", "Terraform", "ArgoCD", "OpenTelemetry", "Datadog", "Python", "Go"],
        "gt_soft": ["reliability mindset", "incident response"],
        "gt_years": 5,
    },
    {
        "id": "p08",
        "resume": {
            "name": "Anjali Menon",
            "summary": "Clinical data manager with 3 years in pharma trials.",
            "experience": [
                {"title": "Clinical Data Manager", "company": "PharmaTrials Inc", "bullets": [
                    "Managed data from Phase II oncology trials.",
                    "Maintained case report forms in Medidata Rave.",
                ]},
            ],
            "skills": ["Medidata Rave", "SAS", "CDASH", "Excel"],
        },
        "jd": (
            "Lead Clinical Data Scientist for Phase III trials. CDISC SDTM ADaM standards, "
            "Veeva Vault EDC, R and Python for statistical programming. "
            "FDA 21 CFR Part 11, risk-based monitoring. CCDM certification preferred."
        ),
        "gt_hard": ["CDISC", "SDTM", "ADaM", "Veeva Vault", "R", "Python", "21 CFR Part 11"],
        "gt_soft": ["regulatory compliance", "attention to detail"],
        "gt_years": 5,
    },
    {
        "id": "p09",
        "resume": {
            "name": "Maria Lopez",
            "summary": "Product manager with 4 years in B2B SaaS.",
            "experience": [
                {"title": "Product Manager", "company": "SaaSBiz", "bullets": [
                    "Managed product roadmap for CRM features.",
                    "Ran weekly sprint planning with engineering team.",
                ]},
            ],
            "skills": ["Jira", "Figma", "SQL", "Confluence"],
        },
        "jd": (
            "Senior Product Manager for payments platform. Experience with API products, "
            "Stripe or Adyen integrations, OKR frameworks, Amplitude analytics, roadmap strategy. "
            "Technical background in fintech required. MBA preferred."
        ),
        "gt_hard": ["Stripe", "Adyen", "Amplitude", "OKR", "API products"],
        "gt_soft": ["strategic thinking", "stakeholder alignment", "roadmap vision"],
        "gt_years": 6,
    },
    {
        "id": "p10",
        "resume": {
            "name": "James Osei",
            "summary": "Security analyst with 3 years in SOC and threat monitoring.",
            "experience": [
                {"title": "Security Analyst", "company": "BankCorp", "bullets": [
                    "Monitored SIEM alerts and triaged incidents.",
                    "Conducted vulnerability scans using Nessus.",
                ]},
            ],
            "skills": ["SIEM", "Nessus", "Splunk", "Python"],
        },
        "jd": (
            "Senior Application Security Engineer. Must have SAST DAST tooling, OWASP Top 10, "
            "AWS security, Kubernetes security hardening, threat modelling, Burp Suite, "
            "and secure SDLC experience. CISSP or CEH certification required."
        ),
        "gt_hard": ["SAST", "DAST", "OWASP", "AWS", "Kubernetes", "Burp Suite", "threat modelling"],
        "gt_soft": ["security mindset", "cross-team collaboration"],
        "gt_years": 5,
    },
]

TASK_MAX_STEPS = {
    "task1_keyword_extraction": 1,
    "task2_bullet_rewrite":     1,
    "task3_full_application":   4,  # summary, experience, skills, cover_letter
}

TASK3_SEQUENCE = ["rewrite_summary", "rewrite_experience", "update_skills", "write_cover_letter"]


# ─────────────────────────────────────────────────────────────────────────────
# GRADER UTILITIES — pure Python, no ML libraries
# ─────────────────────────────────────────────────────────────────────────────

_STOPWORDS = {
    "with", "that", "this", "from", "have", "been", "will", "your", "their",
    "they", "also", "into", "more", "some", "such", "than", "then", "when",
    "where", "which", "while", "would", "about", "after", "before", "should",
    "could", "other", "these", "those", "experience", "required", "looking",
    "hiring", "strong", "using", "must", "plus", "expected", "preferred", "years",
}

_STRONG_VERBS = {
    "achieved", "automated", "built", "created", "delivered", "designed",
    "developed", "drove", "engineered", "established", "generated",
    "implemented", "improved", "increased", "launched", "led", "optimized",
    "reduced", "scaled", "streamlined", "transformed", "analyzed", "architected",
    "accelerated", "deployed", "executed", "managed", "mentored", "spearheaded",
    "coordinated", "owned", "partnered",
}


def _norm(s: str) -> str:
    return s.lower().strip()


def _f1(pred: List[str], gt: List[str]) -> float:
    ps, gs = {_norm(x) for x in pred}, {_norm(x) for x in gt}
    if not ps or not gs:
        return 0.0
    tp = len(ps & gs)
    return round(2 * tp / (len(ps) + len(gs)), 4)


def _jaccard(a: List[str], b: List[str]) -> float:
    sa, sb = {_norm(x) for x in a}, {_norm(x) for x in b}
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return round(len(sa & sb) / len(sa | sb), 4)


def _ats_score(text: str, jd: str) -> float:
    """Keyword overlap between text and JD, stopwords filtered."""
    jd_words = {
        w for w in re.findall(r'\b[a-zA-Z]{3,}\b', jd.lower())
        if w not in _STOPWORDS
    }
    if not jd_words:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for w in jd_words if w in text_lower)
    return round(min(hits / len(jd_words), 1.0), 4)


def _has_number(text: str) -> bool:
    return bool(re.search(r'(\d+%?|\$[\d,]+)', text))


def _starts_strong_verb(text: str) -> bool:
    first = text.strip().lower().split()[0].rstrip('.,') if text.strip() else ""
    return first in _STRONG_VERBS


def _kw_coverage(text: str, keywords: List[str]) -> float:
    if not keywords:
        return 1.0
    tl = text.lower()
    hits = sum(1 for kw in keywords if _norm(kw) in tl)
    return round(hits / len(keywords), 4)


# ─────────────────────────────────────────────────────────────────────────────
# SCORE CLAMP — validator requires strictly 0 < score < 1
# ─────────────────────────────────────────────────────────────────────────────

_EPS = 0.001


def _clamp(score: float) -> float:
    """Ensure score is strictly in (0, 1) as required by the hackathon validator."""
    return round(max(_EPS, min(1.0 - _EPS, float(score))), 4)


def _resume_to_text(r: Dict) -> str:
    parts = [r.get("summary", "")]
    for exp in r.get("experience", []):
        parts.append(exp.get("title", ""))
        parts.extend(exp.get("bullets", []))
    parts.extend(r.get("skills", []))
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────

class ResumeEnvironment(Environment):
    """
    ResumeEnv: Job Application Optimizer.

    3 tasks of increasing difficulty:
      task1_keyword_extraction  (easy)
      task2_bullet_rewrite      (medium)
      task3_full_application    (hard)
    """

    def __init__(self):
        super().__init__()  # sets self.transform and self.rubric (required by base)
        self._state = ResumeState()
        self._pair: Dict = {}
        self._task_id: str = ""
        self._last_grader: Dict = {}

        # Task 3 running state
        self._t3_resume: Dict = {}
        self._t3_cover: str = ""
        self._t3_step_idx: int = 0

    # ── reset ────────────────────────────────────────────────────────────────

    def reset(
        self,
        task_id: str = "task1_keyword_extraction",
        seed: int = None,
        episode_id: str = None,
        **kwargs,
    ) -> ResumeObservation:
        self._task_id = task_id
        self._last_grader = {}

        # If seed provided, use it for pair selection (reproducible across episodes).
        # Falls back to MD5(task_id) so bare reset() is still deterministic.
        if seed is not None:
            idx = int(seed) % len(PAIRS)
        else:
            idx = int(hashlib.md5(task_id.encode()).hexdigest(), 16) % len(PAIRS)
        self._pair = PAIRS[idx]

        self._state = ResumeState(
            task_id=task_id,
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            max_steps=TASK_MAX_STEPS.get(task_id, 1),
            cumulative_reward=0.0,
        )  # episode_id and step_count are Pydantic fields inherited from State base

        # Task 3 — initialise running application from base resume
        self._t3_resume = {
            "summary": self._pair["resume"].get("summary", ""),
            "experience": [dict(e) for e in self._pair["resume"].get("experience", [])],
            "skills": list(self._pair["resume"].get("skills", [])),
        }
        self._t3_cover = ""
        self._t3_step_idx = 0

        return self._initial_obs()

    # ── step ─────────────────────────────────────────────────────────────────

    # Mapping from action_type → task_id for stateless HTTP /step calls.
    _ACTION_TO_TASK = {
        "extract_keywords":  "task1_keyword_extraction",
        "rewrite_bullet":    "task2_bullet_rewrite",
        "rewrite_summary":   "task3_full_application",
        "rewrite_experience":"task3_full_application",
        "update_skills":     "task3_full_application",
        "write_cover_letter":"task3_full_application",
    }

    def step(self, action: ResumeAction) -> ResumeObservation:
        # HTTP /step creates a fresh env with no prior reset().  Auto-initialise
        # using the action_type so stateless calls still return valid rewards.
        if not self._task_id:
            inferred = self._ACTION_TO_TASK.get(action.action_type, "task1_keyword_extraction")
            self.reset(task_id=inferred)

        self._state.step_count += 1

        if self._task_id == "task1_keyword_extraction":
            return self._step_t1(action)
        elif self._task_id == "task2_bullet_rewrite":
            return self._step_t2(action)
        elif self._task_id == "task3_full_application":
            return self._step_t3(action)
        raise ValueError(f"Unknown task_id: {self._task_id}")

    # ── state property ────────────────────────────────────────────────────────

    @property
    def state(self) -> ResumeState:
        return self._state

    # ── task implementations ─────────────────────────────────────────────────

    def _step_t1(self, action: ResumeAction) -> ResumeObservation:
        gt = self._pair
        hard_f1   = _f1(action.hard_skills, gt["gt_hard"])
        soft_jac  = _jaccard(action.soft_skills, gt["gt_soft"])
        exp_diff  = abs(action.experience_years - gt["gt_years"])
        exp_score = max(0.0, 1.0 - exp_diff / max(gt["gt_years"], 1))

        score = _clamp(0.60 * hard_f1 + 0.25 * soft_jac + 0.15 * exp_score)

        self._last_grader = {
            "hard_skill_f1": hard_f1,
            "soft_skill_jaccard": soft_jac,
            "experience_score": round(exp_score, 4),
            "final_score": score,
        }
        self._state.cumulative_reward = score

        return ResumeObservation(
            task_id=self._task_id,
            job_description=self._pair["jd"],
            feedback=(
                f"Hard F1={hard_f1:.2f} | Soft Jaccard={soft_jac:.2f} | "
                f"Exp score={exp_score:.2f}"
            ),
            current_score=score,
            steps_remaining=0,
            done=True,
            reward=score,
            metadata=self._last_grader,
        )

    def _step_t2(self, action: ResumeAction) -> ResumeObservation:
        jd = self._pair["jd"]
        original = self._pair["resume"]["experience"][0]["bullets"][0]
        rewritten = action.rewritten_bullet

        ats_before = _ats_score(original, jd)
        ats_after  = _ats_score(rewritten, jd)
        headroom   = max(1.0 - ats_before, 0.01)
        ats_delta  = min(max((ats_after - ats_before) / headroom, 0.0), 1.0)

        # Semantic preservation: Jaccard over content words
        def _tokens(s):
            return {w for w in re.findall(r'\b[a-z]{3,}\b', s.lower()) if w not in _STOPWORDS}
        ta, tb = _tokens(original), _tokens(rewritten)
        semantic = round(len(ta & tb) / len(ta | tb), 4) if (ta | tb) else 0.0

        quality = round(
            0.5 * float(_has_number(rewritten)) +
            0.5 * float(_starts_strong_verb(rewritten)), 4
        )

        score = _clamp(0.40 * ats_delta + 0.30 * semantic + 0.30 * quality)

        self._last_grader = {
            "ats_before": ats_before,
            "ats_after":  ats_after,
            "ats_delta":  round(ats_delta, 4),
            "semantic_preservation": semantic,
            "quality_score": quality,
            "final_score": score,
        }
        self._state.cumulative_reward = score

        return ResumeObservation(
            task_id=self._task_id,
            job_description=jd,
            resume_snapshot={"original_bullet": original, "rewritten_bullet": rewritten},
            feedback=(
                f"ATS {ats_before:.2f}→{ats_after:.2f} | "
                f"Semantic={semantic:.2f} | Quality={quality:.2f}"
            ),
            current_score=score,
            steps_remaining=0,
            done=True,
            reward=score,
            metadata=self._last_grader,
        )

    def _step_t3(self, action: ResumeAction) -> ResumeObservation:
        jd = self._pair["jd"]
        expected = TASK3_SEQUENCE[self._t3_step_idx] if self._t3_step_idx < len(TASK3_SEQUENCE) else None

        # Apply the action to the running resume state
        partial = 0.0
        if action.action_type == "rewrite_summary":
            self._t3_resume["summary"] = action.content
            partial = _clamp(_ats_score(action.content, jd) * 0.20)

        elif action.action_type == "rewrite_experience":
            bullets = [b.strip() for b in action.content.split("\n") if b.strip()]
            self._t3_resume["experience"] = [{"title": "Rewritten", "bullets": bullets}]
            partial = _clamp(_ats_score(action.content, jd) * 0.25)

        elif action.action_type == "update_skills":
            self._t3_resume["skills"] = [s.strip() for s in action.content.split(",") if s.strip()]
            partial = 0.10

        elif action.action_type == "write_cover_letter":
            self._t3_cover = action.content
            partial = _clamp(_ats_score(action.content, jd) * 0.15)

        self._t3_step_idx += 1
        done = self._t3_step_idx >= len(TASK3_SEQUENCE)

        if done:
            # Final grader
            resume_text = _resume_to_text(self._t3_resume)
            ats   = _ats_score(resume_text, jd)
            cov_r = _ats_score(self._t3_cover, jd) if self._t3_cover else 0.0
            kw_c  = _kw_coverage(resume_text + " " + self._t3_cover, self._pair["gt_hard"])

            # Format checks
            fmt = sum([
                bool(self._t3_resume.get("summary", "").strip()),
                len(self._t3_resume.get("experience", [])) >= 1,
                len(self._t3_resume.get("skills", [])) >= 3,
                len(self._t3_cover) > 80,
                any(g in self._t3_cover.lower() for g in ["dear", "hello", "hi"]),
            ]) / 5.0

            score = _clamp(0.35 * ats + 0.25 * cov_r + 0.25 * kw_c + 0.15 * fmt)

            self._last_grader = {
                "resume_ats": ats,
                "cover_letter_relevance": cov_r,
                "keyword_coverage": kw_c,
                "format_score": round(fmt, 4),
                "final_score": score,
            }
            self._state.cumulative_reward = score
            reward = score
            feedback = f"Final ATS={ats:.2f} | Cover={cov_r:.2f} | KW Coverage={kw_c:.2f} | Format={fmt:.2f}"
        else:
            self._state.cumulative_reward += partial
            reward = partial
            next_step = TASK3_SEQUENCE[self._t3_step_idx]
            feedback = f"✓ {action.action_type} done. Next: {next_step}"

        steps_remaining = max(0, len(TASK3_SEQUENCE) - self._t3_step_idx)

        return ResumeObservation(
            task_id=self._task_id,
            job_description=jd,
            resume_snapshot=self._t3_resume,
            feedback=feedback,
            current_score=reward,
            steps_remaining=steps_remaining,
            done=done,
            reward=reward,
            metadata=self._last_grader if done else {"next_action": TASK3_SEQUENCE[self._t3_step_idx] if not done else "done"},
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _initial_obs(self) -> ResumeObservation:
        jd = self._pair["jd"]
        resume = self._pair["resume"]

        if self._task_id == "task1_keyword_extraction":
            return ResumeObservation(
                task_id=self._task_id,
                job_description=jd,
                feedback=(
                    "Set action_type='extract_keywords'. Provide: "
                    "hard_skills (List[str]), soft_skills (List[str]), experience_years (int)."
                ),
                steps_remaining=1,
                done=False,
            )
        elif self._task_id == "task2_bullet_rewrite":
            original = resume["experience"][0]["bullets"][0]
            return ResumeObservation(
                task_id=self._task_id,
                job_description=jd,
                resume_snapshot={"original_bullet": original},
                feedback=(
                    "Set action_type='rewrite_bullet'. Provide rewritten_bullet. "
                    "Start with a strong verb, add quantification, match JD keywords."
                ),
                steps_remaining=1,
                done=False,
            )
        elif self._task_id == "task3_full_application":
            return ResumeObservation(
                task_id=self._task_id,
                job_description=jd,
                resume_snapshot=self._t3_resume,
                feedback=(
                    f"4-step application. Step 1: set action_type='rewrite_summary', content=new summary. "
                    f"Then: rewrite_experience → update_skills → write_cover_letter."
                ),
                steps_remaining=len(TASK3_SEQUENCE),
                done=False,
            )

    def get_last_grader(self) -> Dict:
        return self._last_grader
