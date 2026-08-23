from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import LLMError
from app.models.enums import ProcessingStatus
from app.schemas.resume_extraction import ResumeExtractionResult


def _make_session():
    from app import models  # noqa: F401
    from app.core.database import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _fake_extraction():
    return ResumeExtractionResult(
        candidate_name="Ada Lovelace",
        candidate_email="ada@example.com",
        skills=[{"name": "Python", "category": "language"}],
        experience=[
            {
                "title": "Engineer",
                "company": "Analytical Engines Inc",
                "start_date": "2020",
                "end_date": None,
                "is_current": True,
                "description": "Wrote the first algorithm.",
            }
        ],
        education=[],
    )


def test_run_structured_extraction_success_sets_completed_and_persists_children():
    from app.repositories import resume_repository
    from app.services.resume_parser import run_structured_extraction

    db = _make_session()
    resume = resume_repository.create_resume(
        db, filename="r.pdf", file_type="pdf", raw_text="some text", content_hash="hash1"
    )

    with patch("app.services.resume_parser.parse_resume", return_value=_fake_extraction()):
        result = run_structured_extraction(db, resume)

    assert result.processing_status == ProcessingStatus.COMPLETED
    assert result.candidate_name == "Ada Lovelace"
    assert len(result.skills) == 1
    assert result.skills[0].raw_text == "Python"
    assert result.experience_entries[0].company == "Analytical Engines Inc"


def test_run_structured_extraction_failure_sets_failed_status_without_raising():
    from app.repositories import resume_repository
    from app.services.resume_parser import run_structured_extraction

    db = _make_session()
    resume = resume_repository.create_resume(
        db, filename="r.pdf", file_type="pdf", raw_text="some text", content_hash="hash2"
    )

    with patch(
        "app.services.resume_parser.parse_resume",
        side_effect=LLMError("simulated provider outage"),
    ):
        result = run_structured_extraction(db, resume)  # must not raise

    assert result.processing_status == ProcessingStatus.FAILED
    assert "simulated provider outage" in result.error_message
    assert result.raw_text == "some text"  # original text still intact
