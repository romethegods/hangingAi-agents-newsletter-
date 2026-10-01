"""Database fixtures for integration tests.

Uses TEST_DATABASE_URL if set (CI provides a Postgres service); otherwise
starts a throwaway local Postgres with pgserver. Schema comes from the real
Alembic migrations, so the migrations are tested too.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings

BACKEND_DIR = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    server = None
    if not url:
        try:
            import pgserver
        except ImportError:
            pytest.skip("set TEST_DATABASE_URL or install pgserver to run DB tests")
        server = pgserver.get_server(
            tempfile.mkdtemp(prefix="hanging-test-pg-"), cleanup_mode="delete"
        )
        url = server.get_uri()
    url = Settings(database_url=url).database_url  # normalize driver prefix
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        capture_output=True,
    )
    yield url
    if server is not None:
        server.cleanup()


@pytest.fixture(scope="session")
async def engine(database_url):
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(engine):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE sources, articles, tools, tool_star_snapshots, tool_releases, users,"
                " arena_battles, arena_model_stats, login_tokens, sessions, follows, briefs,"
                " brief_items RESTART IDENTITY CASCADE"
            )
        )
    return async_sessionmaker(engine, expire_on_commit=False)
