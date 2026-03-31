from __future__ import annotations

from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.job_search.models.profile import UserProfile

BASE_DIR = Path(__file__).resolve().parent.parent  # repo root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys
    groq_api_key: str = ""
    resend_api_key: str = ""
    notification_email: str = ""

    # Groq model selection (override in .env if needed)
    groq_match_model: str = "llama-3.1-8b-instant"       # fast + cheap for scoring
    groq_cover_letter_model: str = "llama-3.3-70b-versatile"  # quality for cover letters

    # Paths
    user_profile_path: Path = BASE_DIR / "config" / "user_profile.yaml"
    db_path: Path = BASE_DIR / "data" / "jobs.db"
    cover_letters_dir: Path = BASE_DIR / "data" / "cover_letters"
    browser_profile_dir: Path = BASE_DIR / "data" / "browser_profile"

    # Matching thresholds
    min_match_score_for_digest: int = 50
    min_match_score_for_cover_letter: int = 70

    def load_profile(self) -> UserProfile:
        raw = yaml.safe_load(self.user_profile_path.read_text())
        return UserProfile(**raw)


# Singleton
settings = Settings()
