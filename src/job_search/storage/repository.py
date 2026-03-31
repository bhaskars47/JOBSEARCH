from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.job_search.models.job import Job
from src.job_search.models.match import MatchResult
from src.job_search.storage.models import ApplicationORM, DigestORM, JobORM


class JobRepository:
    def __init__(self, session: Session):
        self.session = session

    def exists(self, job_id: str) -> bool:
        return self.session.get(JobORM, job_id) is not None

    def upsert(self, job: Job) -> None:
        existing = self.session.get(JobORM, job.job_id)
        if existing:
            existing.last_seen_at = datetime.utcnow()
            existing.is_expired = False
        else:
            self.session.add(JobORM(**job.model_dump()))
        self.session.commit()

    def save_match(self, result: MatchResult) -> None:
        row = self.session.get(JobORM, result.job_id)
        if row:
            row.match_score = result.match_score
            row.recommendation = result.recommendation
            row.match_rationale = result.rationale
            self.session.commit()

    def get_todays_top_jobs(self, min_score: int = 50, limit: int = 30) -> list[JobORM]:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        return (
            self.session.query(JobORM)
            .filter(
                JobORM.first_seen_at >= cutoff,
                JobORM.match_score >= min_score,
                JobORM.is_expired == False,
            )
            .order_by(JobORM.match_score.desc())
            .limit(limit)
            .all()
        )

    def mark_expired(self, days_stale: int = 7) -> None:
        cutoff = datetime.utcnow() - timedelta(days=days_stale)
        (
            self.session.query(JobORM)
            .filter(JobORM.last_seen_at < cutoff, JobORM.is_expired == False)
            .update({"is_expired": True})
        )
        self.session.commit()

    def add_application(self, job_id: str, notes: str = "") -> None:
        self.session.add(ApplicationORM(job_id=job_id, notes=notes))
        self.session.commit()

    def save_digest(self, job_ids: list[str], email_to: str) -> None:
        self.session.add(DigestORM(job_ids=",".join(job_ids), email_to=email_to))
        self.session.commit()
