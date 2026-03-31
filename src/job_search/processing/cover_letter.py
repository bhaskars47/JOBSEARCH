from __future__ import annotations

from pathlib import Path

import httpx
from groq import Groq

from src.job_search.models.job import Job
from src.job_search.models.profile import UserProfile

COVER_LETTER_PROMPT = """\
You are an expert career coach. Write a tailored, professional cover letter for the candidate below.

Guidelines:
- 3-4 paragraphs, concise and compelling
- Open with genuine enthusiasm for the specific role/company
- Highlight 2-3 of the candidate's most relevant skills for THIS job
- Close with a clear call to action
- Do NOT use generic filler phrases like "I am writing to apply..."
- Tone: professional but human, not robotic

Return ONLY the cover letter text. No subject line, no metadata, no extra commentary.
"""


class CoverLetterGenerator:
    def __init__(self, api_key: str, output_dir: Path, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key, http_client=httpx.Client(verify=False))
        self.model = model
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _output_path(self, job_id: str) -> Path:
        return self.output_dir / f"{job_id}.txt"

    def generate(self, job: Job, profile: UserProfile) -> str:
        out_path = self._output_path(job.job_id)
        if out_path.exists():
            return out_path.read_text()

        prompt = f"""\
## Candidate
Name: {profile.name or 'the candidate'}
Skills: {', '.join(profile.skills)}
Years of experience: {profile.years_experience}

## Job
Title: {job.title}
Company: {job.company}
Location: {job.location}
Description:
{job.description[:3000]}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": COVER_LETTER_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1024,
            temperature=0.7,  # slightly higher for creative writing
        )
        letter = response.choices[0].message.content.strip()
        out_path.write_text(letter)
        return letter
