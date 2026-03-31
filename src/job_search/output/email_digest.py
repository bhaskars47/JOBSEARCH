from __future__ import annotations

from datetime import datetime
from pathlib import Path

import resend
from jinja2 import Environment, FileSystemLoader

from src.job_search.storage.models import JobORM

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _enrich(jobs: list[JobORM]) -> list[dict]:
    """Convert ORM rows to template-friendly dicts."""
    return [
        {
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "url": j.url,
            "source": j.source,
            "remote": j.remote,
            "match_score": j.match_score or 0,
            "match_rationale": j.match_rationale or "",
            "recommendation": j.recommendation or "skip",
            "strengths": [],
            "skill_gaps": [],
        }
        for j in jobs
    ]


def send_digest(
    jobs: list[JobORM],
    to_email: str,
    resend_api_key: str,
) -> bool:
    if not jobs:
        print("[Digest] No jobs to send.")
        return False

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("digest.html")

    enriched = _enrich(jobs)
    today = datetime.utcnow().strftime("%B %d, %Y")
    sources = sorted({j["source"] for j in enriched})
    strong_count = sum(1 for j in enriched if j["match_score"] >= 70)
    stretch_count = sum(1 for j in enriched if 50 <= j["match_score"] < 70)

    html_body = template.render(
        jobs=enriched,
        date=today,
        sources=sources,
        strong_count=strong_count,
        stretch_count=stretch_count,
    )

    resend.api_key = resend_api_key
    try:
        r = resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": [to_email],
            "subject": f"[JobSearch] {len(jobs)} new QA roles — {today}",
            "html": html_body,
        })
        print(f"[Digest] Email sent → {to_email} (id: {r.get('id', '?')})")
        return True
    except Exception as e:
        print(f"[Digest] Email failed: {e}")
        return False
