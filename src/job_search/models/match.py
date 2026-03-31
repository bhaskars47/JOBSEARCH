from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MatchResult(BaseModel):
    """Claude API job-profile match output."""

    job_id: str
    match_score: int = Field(ge=0, le=100)
    recommendation: Literal["apply", "stretch", "skip"]
    rationale: str  # 2-3 sentence summary
    strengths: list[str] = []
    skill_gaps: list[str] = []
