from __future__ import annotations

import random
import subprocess
import time
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
from playwright_stealth import Stealth

CAPTCHA_SIGNALS = [
    "captcha", "robot", "verify you are human", "access denied",
    "security check", "cloudflare", "cf-challenge", "unusual traffic",
]


def get_browser_context(browser_profile_dir: Path) -> tuple[Playwright, Browser, BrowserContext]:
    """
    Launch a stealth Chromium browser with persistent storage state.
    Returns (playwright, browser, context) — caller must close all three when done.
    """
    browser_profile_dir.mkdir(parents=True, exist_ok=True)
    state_path = browser_profile_dir / "state.json"

    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=False,  # headed mode avoids many bot-detection signals
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    )

    context_kwargs = dict(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-IN",
        timezone_id="Asia/Kolkata",
    )
    if state_path.exists():
        context_kwargs["storage_state"] = str(state_path)

    context = browser.new_context(**context_kwargs)
    return pw, browser, context


def apply_stealth(page: Page) -> None:
    """Apply playwright-stealth patches to a page."""
    Stealth().apply_stealth_sync(page)


def save_context_state(context: BrowserContext, browser_profile_dir: Path) -> None:
    """Persist cookies and localStorage so next run reuses the session."""
    state_path = browser_profile_dir / "state.json"
    context.storage_state(path=str(state_path))


def close_browser(pw: Playwright, browser: Browser, context: BrowserContext) -> None:
    try:
        context.close()
        browser.close()
        pw.stop()
    except Exception:
        pass


def random_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Sleep a random amount to mimic human browsing pace."""
    time.sleep(random.uniform(min_s, max_s))


def detect_captcha(page: Page) -> bool:
    """Return True if the current page appears to be a CAPTCHA/block page."""
    try:
        title = (page.title() or "").lower()
        content = page.inner_text("body").lower()[:2000]
        combined = title + " " + content
        return any(sig in combined for sig in CAPTCHA_SIGNALS)
    except Exception:
        return False


def notify_captcha(platform: str) -> None:
    """Send a macOS desktop notification alerting the user to solve a CAPTCHA."""
    msg = f"CAPTCHA detected on {platform}. Please solve it in the browser window."
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{msg}" with title "JobSearch Bot"'],
            check=False,
        )
    except Exception:
        pass
    print(f"[{platform}] CAPTCHA detected — waiting 60s for manual solve...")
    time.sleep(60)


def handle_captcha_with_retry(page: Page, platform: str, max_retries: int = 3) -> bool:
    """
    Check for CAPTCHA and retry up to max_retries times.
    Returns True if page is clear, False if still blocked after retries.
    """
    for attempt in range(max_retries):
        if not detect_captcha(page):
            return True
        notify_captcha(platform)
    print(f"[{platform}] Still blocked after {max_retries} retries — skipping.")
    return False
