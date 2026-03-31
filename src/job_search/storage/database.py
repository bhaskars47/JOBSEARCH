from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.job_search.storage.models import Base


def get_engine(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(db_path: Path):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session_factory(db_path: Path):
    engine = init_db(db_path)
    return sessionmaker(bind=engine, expire_on_commit=False)
