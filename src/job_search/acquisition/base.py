from __future__ import annotations

from abc import ABC, abstractmethod

from src.job_search.models.job import Job
from src.job_search.models.profile import UserProfile


class JobSource(ABC):
    """Abstract base class all job source clients must implement."""

    source_name: str = "unknown"

    def __init__(self, profile: UserProfile):
        self.profile = profile

    @abstractmethod
    def fetch_jobs(self) -> list[Job]:
        """Fetch and return a list of Job objects from this source."""
        ...
