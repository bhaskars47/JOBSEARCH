from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl


class Job(BaseModel):
    """Canonical job data contract used across all layers."""

    # Identity
    job_id: str  # composite hash: company_slug + title_slug + location_slug
    source: str  # remoteok | weWorkRemotely | remotive | linkedin | indeed | naukri

    # Core fields
    title: str
    company: str
    location: str
    url: str
    description: str = ""

    # Optional metadata
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    job_type: Optional[str] = None  # full-time | part-time | contract | internship
    remote: bool = False
    posted_at: Optional[datetime] = None

    # Tracking
    first_seen_at: datetime = datetime.utcnow()
    last_seen_at: datetime = datetime.utcnow()
    is_expired: bool = False
