"""
Job Search Automation Pipeline
Entry point for both cron (scheduled) and manual runs.

Usage:
    python -m src.job_search.main                    # full pipeline
    python -m src.job_search.main --dry-run          # fetch + match, no email
    python -m src.job_search.main --apply JOB_ID     # semi-auto apply to a job
    python -m src.job_search.main --apply-top N      # semi-auto apply to top N jobs
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime

from rich.console import Console
from rich.table import Table

from config.settings import settings
from src.job_search.acquisition.indeed import IndeedSource
from src.job_search.acquisition.naukri import NaukriSource
from src.job_search.acquisition.remoteok import RemoteOKSource
from src.job_search.acquisition.rss_feeds import RSSFeedSource
from src.job_search.output.apply import semi_auto_apply
from src.job_search.output.email_digest import send_digest
from src.job_search.processing.matcher import JobMatcher
from src.job_search.storage.database import get_session_factory
from src.job_search.storage.repository import JobRepository

console = Console()


def run(dry_run: bool = False) -> None:
    console.rule(f"[bold blue]JobSearch Pipeline — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    # ── Config & Profile ──────────────────────────────────────────────
    profile = settings.load_profile()
    console.print(f"[dim]Profile loaded: {profile.name or 'unknown'} | {len(profile.target_titles)} target titles[/dim]")

    # ── Storage ───────────────────────────────────────────────────────
    Session = get_session_factory(settings.db_path)
    session = Session()
    repo = JobRepository(session)

    # ── Acquisition ───────────────────────────────────────────────────
    sources = [
        RemoteOKSource(profile),
        RSSFeedSource(profile),
        NaukriSource(profile),   # browser — runs last so API sources always complete
        IndeedSource(profile),   # browser — runs last
    ]

    all_jobs = []
    for src in sources:
        console.print(f"[cyan]Fetching from {src.source_name}...[/cyan]")
        try:
            jobs = src.fetch_jobs()
            console.print(f"  → {len(jobs)} jobs fetched")
            all_jobs.extend(jobs)
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    # ── Deduplication & Storage ───────────────────────────────────────
    new_jobs = []
    for job in all_jobs:
        if not repo.exists(job.job_id):
            repo.upsert(job)
            new_jobs.append(job)
    console.print(f"[green]{len(new_jobs)} new jobs (out of {len(all_jobs)} total)[/green]")

    if not new_jobs:
        console.print("[yellow]No new jobs today. Exiting.[/yellow]")
        return

    # ── Matching ──────────────────────────────────────────────────────
    if not settings.groq_api_key:
        console.print("[red]GROQ_API_KEY not set — skipping match scoring.[/red]")
        return

    console.print(f"[cyan]Scoring {len(new_jobs)} jobs with Groq ({settings.groq_match_model})...[/cyan]")
    matcher = JobMatcher(api_key=settings.groq_api_key, model=settings.groq_match_model)
    results = matcher.score_batch(new_jobs, profile)

    for result in results:
        repo.save_match(result)

    # ── Expire stale jobs ─────────────────────────────────────────────
    repo.mark_expired(days_stale=7)

    # ── CLI Preview ───────────────────────────────────────────────────
    top_jobs = repo.get_todays_top_jobs(min_score=settings.min_match_score_for_digest)
    _print_table(top_jobs)

    # ── Email Digest ──────────────────────────────────────────────────
    if dry_run:
        console.print("[yellow]--dry-run: skipping email send.[/yellow]")
    elif not settings.resend_api_key or not settings.notification_email:
        console.print("[yellow]RESEND_API_KEY or NOTIFICATION_EMAIL not set — skipping email.[/yellow]")
    else:
        sent = send_digest(top_jobs, settings.notification_email, settings.resend_api_key)
        if sent:
            repo.save_digest([j.job_id for j in top_jobs], settings.notification_email)

    console.rule("[bold green]Done")


def _print_table(jobs) -> None:
    table = Table(title=f"Top {len(jobs)} Matched Jobs", show_lines=True)
    table.add_column("Score", style="bold", width=6)
    table.add_column("Title", width=32)
    table.add_column("Company", width=22)
    table.add_column("Location", width=16)
    table.add_column("Rec.", width=8)
    table.add_column("URL", width=40, no_wrap=True)

    for j in jobs:
        score = j.match_score or 0
        color = "green" if score >= 70 else ("yellow" if score >= 50 else "red")
        table.add_row(
            f"[{color}]{score}[/{color}]",
            j.title,
            j.company,
            j.location,
            j.recommendation or "-",
            j.url,
        )

    console.print(table)


def apply_to_jobs(job_ids: list[str]) -> None:
    """Semi-auto apply to specific jobs by ID."""
    profile = settings.load_profile()
    resume_path = profile.resume_path or "~/Documents/Resume.pdf"

    Session = get_session_factory(settings.db_path)
    session = Session()
    repo = JobRepository(session)

    for job_id in job_ids:
        from src.job_search.storage.models import JobORM
        job = session.get(JobORM, job_id)
        if not job:
            console.print(f"[red]Job {job_id} not found in DB.[/red]")
            continue

        console.print(f"\n[bold cyan]Applying to: {job.title} @ {job.company}[/bold cyan]")
        success = semi_auto_apply(
            job=job,
            profile=profile,
            browser_profile_dir=settings.browser_profile_dir,
            resume_path=resume_path,
        )
        if success:
            repo.add_application(job_id=job.job_id, notes="Semi-auto applied via CLI")
            console.print(f"[green]✓ Application recorded for {job.title}[/green]")
        else:
            console.print(f"[yellow]✗ Skipped {job.title}[/yellow]")


def apply_top_n(n: int) -> None:
    """Semi-auto apply to the top N scored jobs."""
    Session = get_session_factory(settings.db_path)
    session = Session()
    from src.job_search.storage.models import JobORM
    top = (
        session.query(JobORM)
        .filter(JobORM.match_score != None, JobORM.is_expired == False)
        .order_by(JobORM.match_score.desc())
        .limit(n)
        .all()
    )
    if not top:
        console.print("[yellow]No scored jobs found.[/yellow]")
        return

    console.print(f"[bold]Applying to top {len(top)} jobs:[/bold]")
    for i, j in enumerate(top, 1):
        console.print(f"  {i}. [{j.match_score}] {j.title} @ {j.company}")

    apply_to_jobs([j.job_id for j in top])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Search Automation Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and match but do not send email")
    parser.add_argument("--apply", type=str, help="Semi-auto apply to a job by ID")
    parser.add_argument("--apply-top", type=int, metavar="N", help="Semi-auto apply to top N scored jobs")
    args = parser.parse_args()

    if args.apply:
        apply_to_jobs([args.apply])
    elif args.apply_top:
        apply_top_n(args.apply_top)
    else:
        run(dry_run=args.dry_run)
