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

BASE_URL = "https://in.indeed.com"
MAX_TITLES = 3   # query at most this many target titles per run
MAX_PAGES = 2    # pages per title query (≈15 jobs/page = 30 max per title)


def _build_search_url(title: str, page: int = 1) -> str:
    params = urllib.parse.urlencode({
        "q": title,
        "l": "India",
        "fromage": "1",  # posted in last 1 day
        "start": (page - 1) * 10,
    })
    return f"{BASE_URL}/jobs?{params}"


class IndeedSource(JobSource):
    source_name = "indeed"

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
                print(f"  [Indeed] Searching: {title}")
                for page_num in range(1, MAX_PAGES + 1):
                    url = _build_search_url(title, page_num)
                    page = context.new_page()
                    apply_stealth(page)
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                        random_delay(2.0, 4.0)

                        if not handle_captcha_with_retry(page, "Indeed"):
                            page.close()
                            break

                        cards = page.query_selector_all(
                            ".job_seen_beacon, [data-jk], .result"
                        )
                        if not cards:
                            page.close()
                            break

                        for card in cards:
                            try:
                                title_el = card.query_selector(
                                    ".jobTitle span, h2.jobTitle a span, [data-testid='jobTitle']"
                                )
                                comp_el = card.query_selector(
                                    ".companyName, [data-testid='company-name'], .company"
                                )
                                loc_el = card.query_selector(
                                    ".companyLocation, [data-testid='text-location'], .location"
                                )
                                desc_el = card.query_selector(
                                    ".job-snippet, .summary, [data-testid='job-snippet']"
                                )
                                jk = card.get_attribute("data-jk")
                                link_el = card.query_selector("h2.jobTitle a, a.jcs-JobTitle")
                                href = link_el.get_attribute("href") if link_el else ""

                                job_title = (title_el.inner_text() if title_el else "").strip()
                                company = (comp_el.inner_text() if comp_el else "").strip()
                                location = (loc_el.inner_text() if loc_el else "India").strip()
                                description = (desc_el.inner_text() if desc_el else "").strip()

                                if not job_title or not company:
                                    continue

                                # Build URL from jk key or href
                                if jk:
                                    job_url = f"{BASE_URL}/viewjob?jk={jk}"
                                elif href:
                                    job_url = href if href.startswith("http") else BASE_URL + href
                                else:
                                    continue

                                job_id = make_job_id(company, job_title, location)
                                if job_id in seen_ids:
                                    continue
                                seen_ids.add(job_id)

                                all_jobs.append(Job(
                                    job_id=job_id,
                                    source=self.source_name,
                                    title=job_title,
                                    company=company,
                                    location=location,
                                    url=job_url,
                                    description=description,
                                    remote="remote" in location.lower(),
                                    posted_at=datetime.utcnow(),
                                ))
                            except Exception:
                                continue

                        random_delay(3.0, 5.0)
                    except Exception as e:
                        print(f"  [Indeed] Error on page {page_num} for '{title}': {e}")
                    finally:
                        page.close()

            save_context_state(context, browser_profile_dir)
        finally:
            close_browser(pw, browser, context)

        print(f"  [Indeed] Total fetched: {len(all_jobs)}")
        return all_jobs
