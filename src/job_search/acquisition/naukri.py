from __future__ import annotations

import urllib.parse
from datetime import datetime

from src.job_search.acquisition.base import JobSource
from src.job_search.acquisition.browser_utils import (
    apply_stealth,
    close_browser,
    get_browser_context,
    handle_captcha_with_retry,
    random_delay,
    save_context_state,
)
from src.job_search.models.job import Job
from src.job_search.models.profile import UserProfile
from src.job_search.processing.deduplication import make_job_id

BASE_URL = "https://www.naukri.com"
MAX_TITLES = 3   # query at most this many target titles per run
MAX_PAGES = 2    # pages per title query (≈20 jobs/page = 40 max per title)


def _build_search_url(title: str, page: int = 1) -> str:
    slug = title.lower().replace(" ", "-")
    params = urllib.parse.urlencode({"k": title, "l": "india", "experience": "5"})
    if page > 1:
        params += f"&start={(page - 1) * 20}"
    return f"{BASE_URL}/jobs?{params}"


def _extract_jobs_from_page(page_content, source_page) -> list[dict]:
    """Extract raw job data from the current Naukri search results page."""
    raw = []
    try:
        # Naukri job cards — multiple selector fallbacks for resilience
        cards = source_page.query_selector_all(
            "article.jobTuple, .srp-jobtuple-wrapper, [data-job-id]"
        )
        for card in cards:
            try:
                title_el = card.query_selector("a.title, .row1 a, .jobTitle a")
                comp_el = card.query_selector(".comp-name, .companyInfo a, .company-name")
                loc_el = card.query_selector(".locWdth, .location, .loc")
                desc_el = card.query_selector(".job-desc, .job-description, .job-snippet")
                link_el = card.query_selector("a.title, .row1 a, a[href*='/job-listings']")

                title = (title_el.inner_text() if title_el else "").strip()
                company = (comp_el.inner_text() if comp_el else "").strip()
                location = (loc_el.inner_text() if loc_el else "India").strip()
                description = (desc_el.inner_text() if desc_el else "").strip()
                href = link_el.get_attribute("href") if link_el else ""

                if not title or not company or not href:
                    continue

                # Ensure absolute URL
                url = href if href.startswith("http") else BASE_URL + href

                raw.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": url,
                    "description": description,
                })
            except Exception:
                continue
    except Exception:
        pass
    return raw


class NaukriSource(JobSource):
    source_name = "naukri"

    def __init__(self, profile: UserProfile, browser_profile_dir=None):
        super().__init__(profile)
        self._browser_profile_dir = browser_profile_dir

    def fetch_jobs(self) -> list[Job]:
        from config.settings import settings
        browser_profile_dir = self._browser_profile_dir or settings.browser_profile_dir

        titles_to_search = self.profile.target_titles[:MAX_TITLES]
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        pw, browser, context = get_browser_context(browser_profile_dir)
        try:
            for title in titles_to_search:
                print(f"  [Naukri] Searching: {title}")
                for page_num in range(1, MAX_PAGES + 1):
                    url = _build_search_url(title, page_num)
                    page = context.new_page()
                    apply_stealth(page)
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                        random_delay(2.0, 4.0)

                        if not handle_captcha_with_retry(page, "Naukri"):
                            page.close()
                            break

                        raw_jobs = _extract_jobs_from_page(None, page)
                        if not raw_jobs:
                            page.close()
                            break

                        for r in raw_jobs:
                            job_id = make_job_id(r["company"], r["title"], r["location"])
                            if job_id in seen_ids:
                                continue
                            seen_ids.add(job_id)
                            all_jobs.append(Job(
                                job_id=job_id,
                                source=self.source_name,
                                title=r["title"],
                                company=r["company"],
                                location=r["location"],
                                url=r["url"],
                                description=r["description"],
                                remote="remote" in r["location"].lower(),
                                posted_at=datetime.utcnow(),
                            ))

                        random_delay(3.0, 5.0)
                    except Exception as e:
                        print(f"  [Naukri] Error on page {page_num} for '{title}': {e}")
                    finally:
                        page.close()

            save_context_state(context, browser_profile_dir)
        finally:
            close_browser(pw, browser, context)

        print(f"  [Naukri] Total fetched: {len(all_jobs)}")
        return all_jobs
