from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx

from src.job_search.acquisition.base import JobSource
from src.job_search.models.job import Job
from src.job_search.models.profile import UserProfile
from src.job_search.processing.deduplication import make_job_id

# RSS/Atom feeds that are ToS-compliant and don't require auth
RSS_SOURCES = [
    {
        "name": "WeWorkRemotely QA",
        "url": "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
        "source_id": "weworkremotely",
        "remote": True,
    },
    {
        "name": "Remotive QA",
        "url": "https://remotive.com/rss/software-dev",
        "source_id": "remotive",
        "remote": True,
    },
]

QA_KEYWORDS = ["qa", "quality", "test", "sdet", "automation engineer"]


def _is_qa_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in QA_KEYWORDS)


def _parse_date(entry) -> Optional[datetime]:
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    return None


class RSSFeedSource(JobSource):
    source_name = "rss"

    def fetch_jobs(self) -> list[Job]:
        jobs: list[Job] = []
        for feed_cfg in RSS_SOURCES:
            try:
                feed = feedparser.parse(feed_cfg["url"])
            except Exception as e:
                print(f"[RSS:{feed_cfg['source_id']}] parse failed: {e}")
                continue

            for entry in feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                if not _is_qa_relevant(title, summary):
                    continue

                link = entry.get("link", "")
                # Extract company from title format "Company: Title" or "Title at Company"
                company = "Unknown"
                if " at " in title:
                    parts = title.rsplit(" at ", 1)
                    title = parts[0].strip()
                    company = parts[1].strip()
                elif ": " in title:
                    parts = title.split(": ", 1)
                    company = parts[0].strip()
                    title = parts[1].strip()

                location = "Remote" if feed_cfg.get("remote") else "Unknown"

                jobs.append(
                    Job(
                        job_id=make_job_id(company, title, location),
                        source=feed_cfg["source_id"],
                        title=title,
                        company=company,
                        location=location,
                        url=link,
                        description=re.sub(r"<[^>]+>", "", summary),  # strip HTML tags
                        remote=feed_cfg.get("remote", False),
                        posted_at=_parse_date(entry),
                    )
                )

        return jobs
