from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class UserProfile(BaseModel):
    target_titles: list[str]
    skills: list[str]
    years_experience: int
    target_locations: list[str]
    salary_min: int = 0
    excluded_companies: list[str] = []
    excluded_industries: list[str] = []
    resume_path: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
