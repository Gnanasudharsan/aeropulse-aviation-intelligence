from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    return create_engine(
        s.database_url,
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_pre_ping=True,  # survive serverless Postgres auto-suspend
        pool_recycle=300,
        connect_args={
            "connect_timeout": 10,
            "application_name": "aeropulse",
            # None disables prepared statements (required behind PgBouncer-style poolers).
            "prepare_threshold": s.db_prepare_threshold or None,
        },
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for jobs/CLI: commit on success, rollback on error."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: read-mostly request session."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
