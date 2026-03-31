from __future__ import annotations

import json

import httpx
from groq import Groq

from src.job_search.models.job import Job
from src.job_search.models.match import MatchResult
from src.job_search.models.profile import UserProfile

MATCH_SYSTEM_PROMPT = """\
You are a career advisor helping a QA professional find the best-fit jobs.
Given a job description and the candidate's profile, evaluate fit and return JSON.

Return ONLY a valid JSON object with these exact keys:
{
  "match_score": <integer 0-100>,
  "recommendation": <"apply" | "stretch" | "skip">,
  "rationale": "<2-3 sentence summary of fit>",
  "strengths": ["<strength1>", "..."],
  "skill_gaps": ["<gap1>", "..."]
}

Guidelines:
- 80-100: Strong match → "apply"
- 60-79: Good fit with minor gaps → "apply"
- 40-59: Stretch role → "stretch"
- 0-39: Poor fit → "skip"

Return ONLY the JSON object. No markdown, no explanation, no code fences.
"""


def _build_user_message(job: Job, profile: UserProfile) -> str:
    return f"""\
## Candidate Profile
- Target titles: {', '.join(profile.target_titles)}
- Skills: {', '.join(profile.skills)}
- Years of experience: {profile.years_experience}
- Preferred locations: {', '.join(profile.target_locations)}

## Job Listing
- Title: {job.title}
- Company: {job.company}
- Location: {job.location}
- Remote: {job.remote}
- Description:
{job.description[:3000]}
"""


class JobMatcher:
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        # verify=False: Homebrew Python 3.14 SSL cert chain issue on this machine
        self.client = Groq(api_key=api_key, http_client=httpx.Client(verify=False))
        self.model = model

    def score(self, job: Job, profile: UserProfile) -> MatchResult:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": MATCH_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(job, profile)},
            ],
            max_tokens=512,
            temperature=0.2,  # low temp for consistent structured output
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if model adds them anyway
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)
        return MatchResult(job_id=job.job_id, **data)

    def score_batch(self, jobs: list[Job], profile: UserProfile) -> list[MatchResult]:
        results = []
        for job in jobs:
            try:
                results.append(self.score(job, profile))
            except Exception as e:
                print(f"[Matcher] failed for {job.job_id} ({job.title}): {e}")
        return results
