"""
Tests for the global catch-all exception handler in app/main.py -- the
backstop for any bare Exception that isn't one of the app's own AppError
subclasses (i.e. a genuine bug slipping past the service layer). Confirms
it returns a generic 500 envelope and never leaks the real exception
message or a traceback to the client.

Uses its own TestClient (raise_server_exceptions=False) rather than the
shared `client` fixture in conftest.py: Starlette's ServerErrorMiddleware
always re-raises the original exception after invoking a custom handler
(so servers can log it / tests can optionally see it) -- the default
TestClient re-raises it too, which would hide the handler's actual JSON
response from this test.
"""
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def lenient_client():
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

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    os.unlink(db_path)


def test_unhandled_exception_returns_generic_500_without_leaking_detail(lenient_client):
    with patch(
        "app.repositories.resume_repository.list_all",
        side_effect=RuntimeError("sensitive internal detail: db path /secret/app.db"),
    ):
        resp = lenient_client.get("/api/resumes")

    assert resp.status_code == 500
    body = resp.json()
    assert body == {"error": {"code": "internal_error", "message": "An unexpected error occurred."}}
    assert "sensitive internal detail" not in resp.text
    assert "/secret/app.db" not in resp.text
