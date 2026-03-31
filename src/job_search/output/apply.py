"""
Semi-Auto Apply Module
Opens the job application page, pre-fills form fields, uploads resume,
and PAUSES for user review before submitting.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from src.job_search.acquisition.browser_utils import (
    apply_stealth,
    close_browser,
    detect_captcha,
    get_browser_context,
    notify_captcha,
    random_delay,
    save_context_state,
)
from src.job_search.models.profile import UserProfile
from src.job_search.storage.models import ApplicationORM, JobORM


def _notify_user(title: str, message: str) -> None:
    """macOS desktop notification."""
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "{title}"'],
            check=False,
        )
    except Exception:
        pass


def _try_fill(page, selectors: list[str], value: str) -> bool:
    """Try multiple CSS selectors to fill a form field. Returns True if filled."""
    if not value:
        return False
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                el.fill(value)
                return True
        except Exception:
            continue
    return False


def _try_upload_resume(page, selectors: list[str], resume_path: str) -> bool:
    """Try to upload resume via file input."""
    expanded = os.path.expanduser(resume_path)
    if not Path(expanded).exists():
        print(f"  [Apply] Resume not found at {expanded}")
        return False
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.set_input_files(expanded)
                print(f"  [Apply] Resume uploaded: {expanded}")
                return True
        except Exception:
            continue
    return False


def _prefill_indeed(page, profile: UserProfile, resume_path: str) -> dict:
    """Pre-fill Indeed application form fields."""
    filled = {}

    # Indeed "Easy Apply" often has these fields
    name_selectors = [
        "input[name='applicant.name']",
        "input[id*='name']",
        "input[aria-label*='name' i]",
        "input[placeholder*='name' i]",
        "#input-applicant.name",
    ]
    email_selectors = [
        "input[name='applicant.email']",
        "input[type='email']",
        "input[id*='email']",
        "input[aria-label*='email' i]",
    ]
    phone_selectors = [
        "input[name='applicant.phoneNumber']",
        "input[type='tel']",
        "input[id*='phone']",
        "input[aria-label*='phone' i]",
    ]
    resume_selectors = [
        "input[type='file']",
        "input[name*='resume']",
        "input[accept*='pdf']",
    ]

    if _try_fill(page, name_selectors, profile.name or ""):
        filled["name"] = True
    if _try_fill(page, email_selectors, profile.email or ""):
        filled["email"] = True
    if _try_fill(page, phone_selectors, profile.phone or ""):
        filled["phone"] = True
    if _try_upload_resume(page, resume_selectors, resume_path):
        filled["resume"] = True

    return filled


def _prefill_naukri(page, profile: UserProfile, resume_path: str) -> dict:
    """Pre-fill Naukri application form fields."""
    filled = {}

    name_selectors = [
        "input[name='name']",
        "input[id*='name']",
        "input[placeholder*='name' i]",
    ]
    email_selectors = [
        "input[name='email']",
        "input[type='email']",
        "input[id*='email']",
    ]
    phone_selectors = [
        "input[name='mobile']",
        "input[name='phone']",
        "input[type='tel']",
        "input[id*='mobile']",
    ]
    resume_selectors = [
        "input[type='file']",
        "input[name*='resume']",
        "input[name*='cv']",
    ]

    if _try_fill(page, name_selectors, profile.name or ""):
        filled["name"] = True
    if _try_fill(page, email_selectors, profile.email or ""):
        filled["email"] = True
    if _try_fill(page, phone_selectors, profile.phone or ""):
        filled["phone"] = True
    if _try_upload_resume(page, resume_selectors, resume_path):
        filled["resume"] = True

    return filled


def semi_auto_apply(
    job: JobORM,
    profile: UserProfile,
    browser_profile_dir: Path,
    resume_path: str = "~/Documents/Resume.pdf",
) -> bool:
    """
    Open the job URL, attempt to pre-fill the application form,
    then PAUSE and wait for user to review + submit manually.

    Returns True if the apply flow completed (user had the chance to submit).
    """
    print(f"\n{'='*60}")
    print(f"  Applying to: {job.title}")
    print(f"  Company:     {job.company}")
    print(f"  Source:      {job.source}")
    print(f"  URL:         {job.url}")
    print(f"{'='*60}")

    pw, browser, context = get_browser_context(browser_profile_dir)
    try:
        page = context.new_page()
        apply_stealth(page)

        # Navigate to job page
        print("  [Apply] Opening job page...")
        page.goto(job.url, wait_until="domcontentloaded", timeout=30_000)
        random_delay(2.0, 3.0)

        if detect_captcha(page):
            notify_captcha(job.source)
            if detect_captcha(page):
                print("  [Apply] CAPTCHA still present — please solve it in the browser.")

        # Look for Apply button and click it
        apply_clicked = False
        apply_btn_selectors = [
            # Indeed
            "button[id*='applyButton']",
            "button.jobsearch-IndeedApplyButton",
            "a[href*='apply']",
            "button:has-text('Apply')",
            "a:has-text('Apply now')",
            "a:has-text('Apply on company site')",
            # Naukri
            "button#apply-button",
            "button.apply-button",
            "a.apply-btn",
            "button:has-text('Apply')",
            # Generic
            "[data-testid*='apply']",
        ]
        for sel in apply_btn_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    apply_clicked = True
                    print(f"  [Apply] Clicked apply button: {sel}")
                    random_delay(2.0, 3.0)
                    break
            except Exception:
                continue

        if not apply_clicked:
            print("  [Apply] No apply button found on page — you may need to click it manually.")

        # Try to pre-fill form fields based on source
        filled = {}
        if job.source == "indeed":
            filled = _prefill_indeed(page, profile, resume_path)
        elif job.source == "naukri":
            filled = _prefill_naukri(page, profile, resume_path)
        else:
            # Generic attempt
            filled = _prefill_indeed(page, profile, resume_path)

        if filled:
            print(f"  [Apply] Pre-filled fields: {', '.join(filled.keys())}")
        else:
            print("  [Apply] Could not auto-fill any fields — fill them manually in the browser.")

        # ── PAUSE: Wait for user to review and submit ──
        _notify_user(
            "JobSearch — Ready to Submit",
            f"Application for {job.title} at {job.company} is ready for review. Check the browser window.",
        )

        print()
        print("  ┌─────────────────────────────────────────────────────┐")
        print("  │  PAUSED — Review the application in the browser.    │")
        print("  │  Submit it manually when ready.                     │")
        print("  │                                                     │")
        print("  │  Press ENTER here when done (or 'skip' to cancel)   │")
        print("  └─────────────────────────────────────────────────────┘")
        print()

        user_input = input("  → ").strip().lower()
        if user_input == "skip":
            print("  [Apply] Skipped by user.")
            return False

        save_context_state(context, browser_profile_dir)
        print("  [Apply] Done! Browser session saved.")
        return True

    except Exception as e:
        print(f"  [Apply] Error: {e}")
        return False
    finally:
        # Don't close browser immediately — let user finish if still reviewing
        try:
            save_context_state(context, browser_profile_dir)
            close_browser(pw, browser, context)
        except Exception:
            pass
