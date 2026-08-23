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
    Gemini -- see app/core/llm_client.py). Pin known defaults here so the
    suite is hermetic; individual tests that care about a specific
    provider (e.g. the Gemini-path tests in test_llm_client.py) still
    monkeypatch further on top of this baseline."""
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
    os.unlink(db_path)


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name
