"""Test configuration.

Integration tests run against a real PostgreSQL database (default: the docker-compose
service, database ``aeropulse_test``; override with TEST_DATABASE_URL). If the server is
unreachable those tests are skipped, never silently passed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://aeropulse:change-me-locally@localhost:5442/aeropulse_test",
)
os.environ["DATABASE_URL"] = TEST_DB
os.environ["APP_ENV"] = "test"
os.environ["INGEST_TRIGGER_TOKEN"] = "test-token"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["HTTP_RETRY_BASE_DELAY"] = "0"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

_KEEP = {"airports", "alembic_version", "source_status"}


def _ensure_database() -> str | None:
    url = make_url(TEST_DB)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except Exception as exc:
        return f"PostgreSQL unavailable for integration tests: {exc.__class__.__name__}"
    finally:
        admin.dispose()
    return None


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[None]:
    reason = _ensure_database()
    if reason:
        pytest.skip(reason)
    from alembic import command
    from alembic.config import Config

    from app.db.seed import seed_airports
    from app.db.session import session_scope

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "migrations")
    )
    command.upgrade(cfg, "head")
    with session_scope() as s:
        seed_airports(s)
    yield


@pytest.fixture
def db(migrated_db: None) -> Iterator[None]:
    """Clean slate per test (airports + source registry kept)."""
    from app.db.session import get_engine, session_scope
    from app.ingestion.persistence import ensure_source_rows

    engine = get_engine()
    with engine.begin() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            if r[0] not in _KEEP
        ]
        if tables:
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        conn.execute(text("DELETE FROM source_status"))
    with session_scope() as s:
        ensure_source_rows(s)
    yield
