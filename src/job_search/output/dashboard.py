"""
Local web dashboard for reviewing and applying to matched jobs.
Run: uv run python -m src.job_search.output.dashboard
Then open: http://localhost:5100
"""
from __future__ import annotations

import subprocess
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

from config.settings import settings
from src.job_search.storage.database import get_session_factory
from src.job_search.storage.models import ApplicationORM, JobORM

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))

_pipeline_status = {"running": False, "last_run": None, "message": ""}


def _get_session():
    Session = get_session_factory(settings.db_path)
    return Session()


@app.route("/")
def index():
    session = _get_session()
    min_score = int(request.args.get("min_score", 0))
    source_filter = request.args.get("source", "all")
    rec_filter = request.args.get("rec", "all")

    q = session.query(JobORM).filter(JobORM.is_expired == False)

    if min_score > 0:
        q = q.filter(JobORM.match_score >= min_score)
    if source_filter != "all":
        q = q.filter(JobORM.source == source_filter)
    if rec_filter != "all":
        q = q.filter(JobORM.recommendation == rec_filter)

    jobs = q.order_by(
        JobORM.match_score.desc().nullslast(),
        JobORM.first_seen_at.desc(),
    ).all()

    # Get applied job IDs
    applied_ids = {
        r.job_id for r in session.query(ApplicationORM.job_id).all()
    }

    sources = [r[0] for r in session.query(JobORM.source).distinct().all()]
    total = session.query(JobORM).filter(JobORM.is_expired == False).count()
    scored = session.query(JobORM).filter(
        JobORM.match_score.isnot(None), JobORM.is_expired == False
    ).count()

    return render_template(
        "dashboard.html",
        jobs=jobs,
        applied_ids=applied_ids,
        sources=sources,
        total=total,
        scored=scored,
        min_score=min_score,
        source_filter=source_filter,
        rec_filter=rec_filter,
        pipeline_status=_pipeline_status,
    )


@app.route("/apply/<job_id>", methods=["POST"])
def apply_job(job_id):
    session = _get_session()
    job = session.get(JobORM, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    # Record the application
    existing = session.query(ApplicationORM).filter_by(job_id=job_id).first()
    if not existing:
        session.add(ApplicationORM(job_id=job_id, status="applied"))
        session.commit()

    # Open the job URL in the default browser
    import webbrowser
    webbrowser.open(job.url)

    return jsonify({"status": "ok", "url": job.url})


@app.route("/pipeline/run", methods=["POST"])
def run_pipeline():
    if _pipeline_status["running"]:
        return jsonify({"status": "already_running"})

    def _run():
        _pipeline_status["running"] = True
        _pipeline_status["message"] = "Pipeline running..."
        try:
            result = subprocess.run(
                [sys.executable, "-m", "src.job_search.main"],
                capture_output=True, text=True,
                cwd=str(Path(__file__).resolve().parents[4]),
            )
            _pipeline_status["message"] = "Done ✓" if result.returncode == 0 else f"Error: {result.stderr[-200:]}"
        except Exception as e:
            _pipeline_status["message"] = f"Failed: {e}"
        finally:
            _pipeline_status["running"] = False
            _pipeline_status["last_run"] = datetime.utcnow().strftime("%H:%M UTC")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/pipeline/status")
def pipeline_status():
    return jsonify(_pipeline_status)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=False)
