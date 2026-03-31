from __future__ import annotations

import hashlib
import re


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text


def make_job_id(company: str, title: str, location: str) -> str:
    """Stable composite ID to deduplicate jobs across sources."""
    key = f"{_slugify(company)}|{_slugify(title)}|{_slugify(location)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
