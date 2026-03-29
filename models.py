# models.py
# Typed Action, Observation, State models for ResumeEnv.
# Follows exact OpenEnv scaffold: from openenv.core.env_server import Action, Observation, State
# Base classes are Pydantic BaseModel — do NOT use @dataclass decorator.

from typing import Any, Dict, List, Optional
from pydantic import Field
from openenv.core.env_server import Action, Observation, State


class ResumeAction(Action):
    """
    Unified action for all 3 tasks.

    task1 — set action_type="extract_keywords"
        hard_skills: List[str]
        soft_skills: List[str]
        experience_years: int

    task2 — set action_type="rewrite_bullet"
        rewritten_bullet: str

    task3 — set action_type to one of:
        "rewrite_summary" | "rewrite_experience" | "update_skills" | "write_cover_letter"
        content: str
    """
    action_type: str = ""

    # Task 1 fields
    hard_skills: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list)
    experience_years: int = 0

    # Task 2 field
    rewritten_bullet: str = ""

    # Task 3 field
    content: str = ""


class ResumeObservation(Observation):
    """Observation returned after every reset() and step()."""
    task_id: str = ""
    job_description: str = ""
    resume_snapshot: Dict[str, Any] = Field(default_factory=dict)
    feedback: str = ""
    current_score: float = 0.0
    steps_remaining: int = 0
    # done and reward are inherited from Observation base class


class ResumeState(State):
    """Episode metadata."""
    task_id: str = ""
    max_steps: int = 5
    cumulative_reward: float = 0.0
    # episode_id and step_count are inherited from State base class
