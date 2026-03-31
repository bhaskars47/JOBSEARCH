from __future__ import annotations

from datetime import datetime

import httpx

from src.job_search.acquisition.base import JobSource
from src.job_search.models.job import Job
from src.job_search.models.profile import UserProfile
from src.job_search.processing.deduplication import make_job_id

REMOTEOK_API = "https://remoteok.com/api"
QA_TAGS = ["qa", "testing", "quality-assurance", "sdet", "automation"]


class RemoteOKSource(JobSource):
    source_name = "remoteok"

    def fetch_jobs(self) -> list[Job]:
        headers = {"User-Agent": "jobsearch-automation/1.0 (personal project)"}
        try:
            # verify=False: local Homebrew OpenSSL cert chain issue; safe for public read-only API
            resp = httpx.get(REMOTEOK_API, headers=headers, timeout=15, verify=False)
            resp.raise_for_status()
        except Exception as e:
            print(f"[RemoteOK] fetch failed: {e}")
            return []

        data = resp.json()
        if not isinstance(data, list):
            return []

        jobs: list[Job] = []
        for item in data[1:]:  # first element is metadata
            if not isinstance(item, dict):
                continue
            tags = [t.lower() for t in item.get("tags", [])]
            title = item.get("position", "")

            # Filter: must relate to QA/testing or match target titles
            title_lower = title.lower()
            is_qa = any(tag in tags for tag in QA_TAGS) or any(
                kw in title_lower
                for kw in ["qa", "quality", "test", "sdet", "automation"]
            )
            if not is_qa:
                continue

            company = item.get("company", "Unknown")
            location = item.get("location") or "Remote"
            url = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"

            posted_at = None
            if item.get("date"):
                try:
                    posted_at = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                except Exception:
                    pass

            jobs.append(
                Job(
                    job_id=make_job_id(company, title, location),
                    source=self.source_name,
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    description=item.get("description", ""),
                    remote=True,
                    posted_at=posted_at,
                )
            )

        return jobs
