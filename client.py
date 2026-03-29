# client.py
# ResumeEnv client — subclasses HTTPEnvClient exactly as shown in OpenEnv envs/README.md
# Usage:
#   async with ResumeEnv(base_url="https://your-hf-space.hf.space") as env:
#       result = await env.reset(task_id="task1_keyword_extraction")
#       result = await env.step(ResumeAction(action_type="extract_keywords", hard_skills=["SQL"]))
#
#   # Sync usage:
#   with ResumeEnv(base_url="http://localhost:8000").sync() as env:
#       result = env.reset()
#       result = env.step(ResumeAction(...))

from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult

from models import ResumeAction, ResumeObservation, ResumeState


class ResumeEnv(EnvClient[ResumeAction, ResumeObservation, ResumeState]):

    def _step_payload(self, action: ResumeAction) -> dict:
        return {
            "action_type":       action.action_type,
            "hard_skills":       action.hard_skills,
            "soft_skills":       action.soft_skills,
            "experience_years":  action.experience_years,
            "rewritten_bullet":  action.rewritten_bullet,
            "content":           action.content,
        }

    def _parse_result(self, payload: dict) -> StepResult[ResumeObservation]:
        obs_data = payload.get("observation", payload)  # handle flat or nested
        obs = ResumeObservation(
            task_id=obs_data.get("task_id", ""),
            job_description=obs_data.get("job_description", ""),
            resume_snapshot=obs_data.get("resume_snapshot", {}),
            feedback=obs_data.get("feedback", ""),
            current_score=obs_data.get("current_score", 0.0),
            steps_remaining=obs_data.get("steps_remaining", 0),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=obs,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: dict) -> ResumeState:
        return ResumeState(
            task_id=payload.get("task_id", ""),
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            max_steps=payload.get("max_steps", 1),
            cumulative_reward=payload.get("cumulative_reward", 0.0),
        )
