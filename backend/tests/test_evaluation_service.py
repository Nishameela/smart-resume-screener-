from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import LLMError, NotFoundError, ValidationAppError
from app.models.enums import LLMStatus, ProcessingStatus
from app.schemas.evaluation_llm import EvaluationLLMResult
from app.services import llm_evaluator
from app.services.deterministic_matcher import DeterministicEvidence


def _make_session():
    from app import models  # noqa: F401
    from app.core.database import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_resume_and_jd(db, *, resume_status=ProcessingStatus.COMPLETED):
    from app.models.enums import RequirementCategory, RequirementPriority, SkillMatchType
    from app.models.job_description import JDRequirement, JobDescription
    from app.models.resume import ExperienceEntry, Resume, ResumeSkill

    resume = Resume(
        filename="r.pdf",
        file_type="pdf",
        raw_text="Built REST APIs using Python and FastAPI at Acme Corp.",
        content_hash="hash-eval-1",
        candidate_name="Jordan Lee",
        processing_status=resume_status,
    )
    resume.skills.append(
        ResumeSkill(raw_text="Python", canonical_name="Python", category="language", match_type=SkillMatchType.EXACT)
    )
    resume.experience_entries.append(
        ExperienceEntry(title="Engineer", company="Acme", start_date="2020", end_date=None, is_current=True)
    )
    db.add(resume)

    jd = JobDescription(raw_text="Need a Python backend engineer.", job_title="Backend Engineer", content_hash="jd-hash-1")
    jd.requirements.append(
        JDRequirement(requirement_text="Python experience", priority=RequirementPriority.MUST_HAVE, category=RequirementCategory.SKILL)
    )
    jd.requirements.append(
        JDRequirement(requirement_text="AWS experience", priority=RequirementPriority.PREFERRED, category=RequirementCategory.SKILL)
    )
    db.add(jd)
    db.commit()
    db.refresh(resume)
    db.refresh(jd)
    return resume, jd


def _fake_grounded_evaluation(jd):
    deterministic_by_index = {
        1: DeterministicEvidence(category="skill", matched=True, score=100.0, summary="Python found."),
        2: DeterministicEvidence(category="skill", matched=False, score=0.0, summary="AWS not found."),
    }
    requirement_by_index = {i: req for i, req in enumerate(jd.requirements, start=1)}
    llm_result = EvaluationLLMResult(
        requirement_matches=[
            {
                "requirement_index": 1,
                "match_level": "strong",
                "evidence": ["Built REST APIs using Python and FastAPI"],
                "reasoning": "Direct evidence of Python backend work.",
                "confidence": 0.95,
            },
            {
                "requirement_index": 2,
                "match_level": "not_demonstrated",
                "evidence": [],
                "reasoning": "No AWS mention in the resume.",
                "confidence": 0.9,
            },
        ],
        summary={
            "strengths": ["Strong Python backend experience"],
            "gaps": ["No AWS experience demonstrated"],
            "executive_summary": "A strong candidate for further review.",
            "interview_focus_areas": ["Cloud infrastructure experience"],
        },
    )
    return llm_evaluator.GroundedEvaluation(
        llm_result=llm_result,
        deterministic_by_index=deterministic_by_index,
        requirement_by_index=requirement_by_index,
    )


def test_successful_evaluation_persists_correct_scores_and_status():
    from app.services.evaluation_service import get_or_create_evaluation

    db = _make_session()
    resume, jd = _seed_resume_and_jd(db)

    with patch.object(llm_evaluator, "run_grounded_evaluation", return_value=_fake_grounded_evaluation(jd)):
        evaluation = get_or_create_evaluation(db, resume.id, jd.id)

    assert evaluation.llm_status == LLMStatus.SUCCESS
    # must_have strong (100*2) + preferred not_demonstrated (0*1) = 200/3 = 66.7, no penalty (no missing must-have)
    assert evaluation.overall_score == round(200 / 3, 1)
    assert evaluation.ai_summary == "A strong candidate for further review."
    assert len(evaluation.requirement_matches) == 2
    assert evaluation.deterministic_component == round((100.0 * 2 + 0.0 * 1) / 3, 1)


def test_evaluation_is_idempotent_and_does_not_recall_llm():
    from app.services.evaluation_service import get_or_create_evaluation

    db = _make_session()
    resume, jd = _seed_resume_and_jd(db)

    with patch.object(
        llm_evaluator, "run_grounded_evaluation", return_value=_fake_grounded_evaluation(jd)
    ) as mock_run:
        first = get_or_create_evaluation(db, resume.id, jd.id)
        second = get_or_create_evaluation(db, resume.id, jd.id)

    assert first.id == second.id
    mock_run.assert_called_once()


def test_llm_failure_falls_back_to_deterministic_only_scoring():
    from app.services.evaluation_service import get_or_create_evaluation

    db = _make_session()
    resume, jd = _seed_resume_and_jd(db)

    with patch.object(llm_evaluator, "run_grounded_evaluation", side_effect=LLMError("provider outage")):
        evaluation = get_or_create_evaluation(db, resume.id, jd.id)

    assert evaluation.llm_status == LLMStatus.FALLBACK
    assert "provider outage" in evaluation.ai_summary
    assert "deterministic" in evaluation.ai_summary.lower()
    assert len(evaluation.requirement_matches) == 2
    # Python requirement should still show a deterministic strong match
    python_match = next(m for m in evaluation.requirement_matches if m.requirement.requirement_text == "Python experience")
    assert python_match.match_level.value == "strong"


def test_nonexistent_resume_raises_not_found():
    from app.services.evaluation_service import get_or_create_evaluation

    db = _make_session()
    _, jd = _seed_resume_and_jd(db)
    try:
        get_or_create_evaluation(db, 999, jd.id)
        assert False, "expected NotFoundError"
    except NotFoundError:
        pass


def test_nonexistent_jd_raises_not_found():
    from app.services.evaluation_service import get_or_create_evaluation

    db = _make_session()
    resume, _ = _seed_resume_and_jd(db)
    try:
        get_or_create_evaluation(db, resume.id, 999)
        assert False, "expected NotFoundError"
    except NotFoundError:
        pass


def test_resume_not_completed_raises_validation_error():
    from app.services.evaluation_service import get_or_create_evaluation

    db = _make_session()
    resume, jd = _seed_resume_and_jd(db, resume_status=ProcessingStatus.FAILED)
    try:
        get_or_create_evaluation(db, resume.id, jd.id)
        assert False, "expected ValidationAppError"
    except ValidationAppError as e:
        assert "not completed" in e.message or "has not completed" in e.message


def _minimal_evaluation_fields(resume_id, jd_id):
    return dict(
        resume_id=resume_id,
        jd_id=jd_id,
        overall_score=50.0,
        deterministic_component=50.0,
        llm_component=50.0,
        confidence=0.5,
        ai_summary="test",
        strengths=[],
        gaps=[],
        interview_focus_areas=[],
        llm_status=LLMStatus.SUCCESS,
        requirement_matches=[],
    )


def test_create_or_fetch_existing_returns_winner_after_losing_race():
    """Simulates two concurrent requests for the same (resume_id, jd_id):
    the first insert wins and commits; the second hits the unique
    constraint's IntegrityError and should transparently return the row
    the first request created, rather than raising a 500."""
    from app.services.evaluation_service import _create_or_fetch_existing

    db = _make_session()
    resume, jd = _seed_resume_and_jd(db)

    winner = _create_or_fetch_existing(db, resume.id, jd.id, _minimal_evaluation_fields(resume.id, jd.id))

    # Second "concurrent" attempt for the same pair must not create a
    # duplicate row -- it should lose to the unique constraint and be
    # handed back the winner's row instead.
    loser_attempt = _create_or_fetch_existing(db, resume.id, jd.id, _minimal_evaluation_fields(resume.id, jd.id))

    assert loser_attempt.id == winner.id
    assert db.query(type(winner)).filter_by(resume_id=resume.id, jd_id=jd.id).count() == 1


def test_create_or_fetch_existing_reraises_when_not_actually_a_duplicate():
    """If create_evaluation raises IntegrityError for a reason other than
    the (resume_id, jd_id) unique constraint actually being duplicated
    (e.g. a genuine data-integrity problem), the fallback lookup finds
    nothing and the original error must propagate rather than being
    swallowed."""
    from sqlalchemy.exc import IntegrityError

    from app.repositories import evaluation_repository
    from app.services.evaluation_service import _create_or_fetch_existing

    db = _make_session()
    resume, jd = _seed_resume_and_jd(db)

    with patch.object(
        evaluation_repository, "create_evaluation", side_effect=IntegrityError("stmt", {}, Exception("boom"))
    ):
        try:
            _create_or_fetch_existing(db, resume.id, jd.id, _minimal_evaluation_fields(resume.id, jd.id))
            assert False, "expected IntegrityError to propagate"
        except IntegrityError:
            pass
