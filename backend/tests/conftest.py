"""
Shared pytest fixtures. The API test client uses an isolated, file-based
SQLite DB (deleted after the test) instead of the app's real data/app.db,
so tests never depend on or pollute developer/demo state.
"""
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolate_llm_settings(monkeypatch):
    """The same isolation principle as the `client` fixture below, applied
    to LLM config: tests must behave identically no matter what
    LLM_PROVIDER / API keys / model happen to be set in the developer's
    real backend/.env (which, for real usage, is deliberately pointed at
    Gemini -- see app/core/llm_client.py), and independently of
    Settings.llm_provider's own default (also "gemini", see config.py).
    Pinning this fixture to "anthropic" is a deliberate, fixed test
    baseline -- most pre-existing tests were written expecting
    Anthropic-flavored behavior (e.g. "ANTHROPIC_API_KEY" in error
    messages) -- not an attempt to mirror either the real or default
    provider. Individual tests that care about a specific provider (e.g.
    the Gemini-path tests in test_llm_client.py) monkeypatch further on
    top of this baseline."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "llm_model_default", "")
    monkeypatch.setattr(settings, "llm_model_extraction", None)
    monkeypatch.setattr(settings, "llm_model_evaluation", None)


@pytest.fixture()
def client():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    from app import models  # noqa: F401  registers models on Base.metadata
    from app.core.database import Base, get_db
    from app.main import app

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    # Release the engine's pooled connections before deleting the file --
    # on Windows, os.unlink() fails with "used by another process" (WinError
    # 32) if any connection in the pool still holds the file open; POSIX
    # silently allows unlinking an open file, which is why this only shows
    # up on Windows.
    test_engine.dispose()
    os.unlink(db_path)


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name
