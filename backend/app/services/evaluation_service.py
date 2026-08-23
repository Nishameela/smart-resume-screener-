"""
Top-level orchestration for "evaluate this resume against this JD":
loads both records, runs the grounded LLM evaluation, and -- this is
the external-LLM-failure plan from the README -- falls back to an
honest deterministic-only score (never a fake/fabricated one) if the
LLM is unavailable, rather than failing the whole request.
"""
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import LLMError, NotFoundError, ValidationAppError
from app.models.enums import LLMStatus, MatchLevel, ProcessingStatus
from app.models.evaluation import Evaluation
from app.repositories import evaluation_repository, jd_repository, resume_repository
from app.services import llm_evaluator
from app.services.scorer import RequirementScoreInput, compute_score

logger = logging.getLogger(__name__)


def get_or_create_evaluation(db: Session, resume_id: int, jd_id: int) -> Evaluation:
    resume = resume_repository.get_by_id(db, resume_id)
    if resume is None:
        raise NotFoundError(f"Resume {resume_id} not found.")
    jd = jd_repository.get_by_id(db, jd_id)
    if jd is None:
        raise NotFoundError(f"Job description {jd_id} not found.")

    if resume.processing_status != ProcessingStatus.COMPLETED:
        raise ValidationAppError(
            f"Resume {resume_id} has not completed structured extraction "
            f"(status={resume.processing_status.value}); it cannot be evaluated yet."
        )
    if not jd.requirements:
        raise ValidationAppError(f"Job description {jd_id} has no extracted requirements.")

    existing = evaluation_repository.get_by_resume_and_jd(db, resume_id, jd_id)
    if existing is not None:
        return existing

    try:
        grounded = llm_evaluator.run_grounded_evaluation(
            resume_text=resume.raw_text,
            resume_skills=resume.skills,
            experience_entries=resume.experience_entries,
            education_entries=resume.education_entries,
            requirements=jd.requirements,
        )
        evaluation_fields = _build_from_grounded_result(grounded, resume_id=resume_id, jd_id=jd_id)
        return _create_or_fetch_existing(db, resume_id, jd_id, evaluation_fields)
    except LLMError as exc:
        logger.warning(
            "Grounded LLM evaluation failed for resume=%s jd=%s: %s. Falling back to "
            "deterministic-only scoring.",
            resume_id,
            jd_id,
            exc,
        )
        return _build_deterministic_fallback(
            db, resume, jd, resume_id=resume_id, jd_id=jd_id, error=str(exc)
        )


def _create_or_fetch_existing(db: Session, resume_id: int, jd_id: int, fields: dict) -> Evaluation:
    """Insert, but tolerate losing a race to a concurrent request for the
    same (resume_id, jd_id) pair: the DB's unique constraint (see
    app/models/evaluation.py) rejects the second insert, so we roll back
    and return whichever evaluation actually made it in, rather than
    surfacing a 500 for what is really just a duplicate-work race."""
    try:
        return evaluation_repository.create_evaluation(db, **fields)
    except IntegrityError:
        db.rollback()
        existing = evaluation_repository.get_by_resume_and_jd(db, resume_id, jd_id)
        if existing is None:
            raise  # not actually a duplicate-key race; something else went wrong
        return existing


def _build_from_grounded_result(
    grounded: llm_evaluator.GroundedEvaluation, *, resume_id: int, jd_id: int
) -> dict:
    match_by_index = {m.requirement_index: m for m in grounded.llm_result.requirement_matches}

    score_inputs: list[RequirementScoreInput] = []
    requirement_matches: list[dict] = []

    for index, requirement in grounded.requirement_by_index.items():
        deterministic = grounded.deterministic_by_index[index]
        llm_match = match_by_index.get(index)

        if llm_match is None:
            # The model skipped a requirement it was asked to evaluate --
            # treat as not_demonstrated with zero confidence rather than
            # silently dropping it from the score.
            logger.warning(
                "LLM omitted requirement index %s (resume=%s jd=%s); treating as not_demonstrated.",
                index,
                resume_id,
                jd_id,
            )
            match_level = MatchLevel.NOT_DEMONSTRATED
            evidence: list[str] = []
            reasoning = "The AI evaluation did not return a judgment for this requirement."
            confidence = 0.0
        else:
            match_level = MatchLevel(llm_match.match_level)
            evidence = llm_match.evidence
            reasoning = llm_match.reasoning
            confidence = llm_match.confidence

        priority = requirement.priority.value if hasattr(requirement.priority, "value") else requirement.priority
        score_inputs.append(
            RequirementScoreInput(
                priority=priority,
                match_level=match_level.value,
                confidence=confidence,
                deterministic_score=deterministic.score,
            )
        )
        requirement_matches.append(
            {
                "requirement_id": requirement.id,
                "match_level": match_level,
                "evidence": evidence,
                "reasoning": reasoning,
                "confidence": confidence,
            }
        )

    breakdown = compute_score(score_inputs)
    summary = grounded.llm_result.summary

    return {
        "resume_id": resume_id,
        "jd_id": jd_id,
        "overall_score": breakdown.overall_score,
        "deterministic_component": breakdown.deterministic_component,
        "llm_component": breakdown.llm_component,
        "confidence": breakdown.confidence,
        "ai_summary": summary.executive_summary,
        "strengths": summary.strengths,
        "gaps": summary.gaps,
        "interview_focus_areas": summary.interview_focus_areas,
        "llm_status": LLMStatus.SUCCESS,
        "requirement_matches": requirement_matches,
    }


# Thresholds for translating a deterministic-only 0-100 score into a
# match_level label when the LLM is unavailable. Coarser than the LLM's
# nuanced judgment by necessity -- this is a degraded, honest fallback,
# not a claim of equivalent quality.
_FALLBACK_STRONG_THRESHOLD = 80.0
_FALLBACK_PARTIAL_THRESHOLD = 40.0


def _deterministic_only_match_level(score: float | None) -> MatchLevel:
    if score is None:
        return MatchLevel.NOT_DEMONSTRATED
    if score >= _FALLBACK_STRONG_THRESHOLD:
        return MatchLevel.STRONG
    if score >= _FALLBACK_PARTIAL_THRESHOLD:
        return MatchLevel.PARTIAL
    if score > 0:
        return MatchLevel.WEAK
    return MatchLevel.NOT_DEMONSTRATED


def _build_deterministic_fallback(
    db: Session, resume, jd, *, resume_id: int, jd_id: int, error: str
) -> Evaluation:
    deterministic_by_index, requirement_by_index = llm_evaluator.compute_deterministic_evidence(
        resume_skills=resume.skills,
        experience_entries=resume.experience_entries,
        education_entries=resume.education_entries,
        requirements=jd.requirements,
    )

    score_inputs: list[RequirementScoreInput] = []
    requirement_matches: list[dict] = []

    for index, requirement in requirement_by_index.items():
        evidence_item = deterministic_by_index[index]
        priority = requirement.priority.value if hasattr(requirement.priority, "value") else requirement.priority

        if evidence_item.score is None:
            # No deterministic signal exists for this requirement at all (e.g. a
            # responsibility/soft-skill requirement -- see deterministic_matcher.py)
            # -- this means "never checked," not "checked and absent." With no LLM
            # available either, we genuinely have no evidence either way, so this
            # requirement is left OUT of score_inputs entirely: it must not drag
            # down the weighted-average score, and it must not count toward the
            # missing-must-have penalty, both of which would misrepresent "unknown"
            # as "confirmed missing." It still gets a requirement_matches row so
            # the UI can show it, honestly labeled as unevaluated.
            requirement_matches.append(
                {
                    "requirement_id": requirement.id,
                    "match_level": MatchLevel.NOT_DEMONSTRATED,
                    "evidence": [],
                    "reasoning": (
                        "AI evaluation was unavailable, and this requirement has no "
                        "deterministic (rule-based) signal either -- it could not be "
                        "evaluated at all and was excluded from the score, rather than "
                        f"counted as unmet. {evidence_item.summary}"
                    ),
                    "confidence": 0.0,
                }
            )
            continue

        match_level = _deterministic_only_match_level(evidence_item.score)
        score_inputs.append(
            RequirementScoreInput(
                priority=priority,
                match_level=match_level.value,
                confidence=0.3,
                deterministic_score=evidence_item.score,
            )
        )
        requirement_matches.append(
            {
                "requirement_id": requirement.id,
                "match_level": match_level,
                "evidence": [],
                "reasoning": (
                    f"AI evaluation was unavailable for this evaluation; this is a "
                    f"deterministic-only estimate. {evidence_item.summary}"
                ),
                "confidence": 0.3,
            }
        )

    breakdown = compute_score(score_inputs)

    fallback_fields = dict(
        resume_id=resume_id,
        jd_id=jd_id,
        overall_score=breakdown.overall_score,
        deterministic_component=breakdown.deterministic_component,
        llm_component=breakdown.llm_component,
        confidence=breakdown.confidence,
        ai_summary=(
            "AI-powered evaluation was unavailable for this candidate "
            f"({error}). The score shown reflects deterministic (rule-based) "
            "matching only -- skill overlap, experience-year arithmetic, and "
            "education-level comparison -- without semantic evidence review."
        ),
        strengths=[],
        gaps=[],
        interview_focus_areas=[],
        llm_status=LLMStatus.FALLBACK,
        requirement_matches=requirement_matches,
    )
    return _create_or_fetch_existing(db, resume_id, jd_id, fallback_fields)
