"""
Unit tests for the race-tolerant "insert, but fall back to fetch on a
lost unique-constraint race" helpers in the resume and JD repositories.

These mirror the equivalent protection added for evaluations
(app/services/evaluation_service.py::_create_or_fetch_existing) -- resumes
and job descriptions have the same "check content_hash, then insert"
pattern in their API routes, so they're exposed to the same theoretical
race between two concurrent requests carrying byte-identical content.
"""
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.schemas.job_description import JDExtractionResult


def _make_session():
    from app import models  # noqa: F401
    from app.core.database import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_create_resume_or_get_existing_returns_winner_after_losing_race():
    from app.repositories import resume_repository

    db = _make_session()
    winner, created_first = resume_repository.create_resume_or_get_existing(
        db, filename="a.pdf", file_type="pdf", raw_text="same text", content_hash="dup-hash"
    )
    loser, created_second = resume_repository.create_resume_or_get_existing(
        db, filename="b.pdf", file_type="pdf", raw_text="same text", content_hash="dup-hash"
    )

    assert created_first is True
    assert created_second is False
    assert loser.id == winner.id
    assert db.query(type(winner)).filter_by(content_hash="dup-hash").count() == 1


def test_create_resume_or_get_existing_reraises_when_not_actually_a_duplicate():
    from app.repositories import resume_repository

    db = _make_session()
    with patch.object(
        resume_repository, "create_resume", side_effect=IntegrityError("stmt", {}, Exception("boom"))
    ):
        try:
            resume_repository.create_resume_or_get_existing(
                db, filename="a.pdf", file_type="pdf", raw_text="text", content_hash="no-match"
            )
            assert False, "expected IntegrityError to propagate"
        except IntegrityError:
            pass


def _fake_extraction():
    return JDExtractionResult(job_title="Backend Engineer", requirements=[])


def test_create_job_description_or_get_existing_returns_winner_after_losing_race():
    from app.repositories import jd_repository

    db = _make_session()
    extraction = _fake_extraction()
    winner, created_first = jd_repository.create_job_description_or_get_existing(
        db, raw_text="same jd text", content_hash="jd-dup-hash", extraction=extraction
    )
    loser, created_second = jd_repository.create_job_description_or_get_existing(
        db, raw_text="same jd text", content_hash="jd-dup-hash", extraction=extraction
    )

    assert created_first is True
    assert created_second is False
    assert loser.id == winner.id
    assert db.query(type(winner)).filter_by(content_hash="jd-dup-hash").count() == 1


def test_create_job_description_or_get_existing_reraises_when_not_actually_a_duplicate():
    from app.repositories import jd_repository

    db = _make_session()
    with patch.object(
        jd_repository, "create_job_description", side_effect=IntegrityError("stmt", {}, Exception("boom"))
    ):
        try:
            jd_repository.create_job_description_or_get_existing(
                db, raw_text="text", content_hash="no-match", extraction=_fake_extraction()
            )
            assert False, "expected IntegrityError to propagate"
        except IntegrityError:
            pass
