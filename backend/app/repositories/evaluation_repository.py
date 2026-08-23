from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.evaluation import Evaluation, RequirementMatch
from app.models.enums import LLMStatus


def get_by_resume_and_jd(db: Session, resume_id: int, jd_id: int) -> Evaluation | None:
    return db.scalar(
        select(Evaluation).where(Evaluation.resume_id == resume_id, Evaluation.jd_id == jd_id)
    )


def get_by_id(db: Session, evaluation_id: int) -> Evaluation | None:
    return db.scalar(
        select(Evaluation)
        .options(selectinload(Evaluation.requirement_matches).selectinload(RequirementMatch.requirement))
        .where(Evaluation.id == evaluation_id)
    )


def list_for_jd(db: Session, jd_id: int) -> list[Evaluation]:
    return list(
        db.scalars(
            select(Evaluation)
            .options(selectinload(Evaluation.resume))
            .where(Evaluation.jd_id == jd_id)
            .order_by(Evaluation.overall_score.desc())
        )
    )


def create_evaluation(
    db: Session,
    *,
    resume_id: int,
    jd_id: int,
    overall_score: float,
    deterministic_component: float | None,
    llm_component: float,
    confidence: float,
    ai_summary: str | None,
    strengths: list[str],
    gaps: list[str],
    interview_focus_areas: list[str],
    llm_status: LLMStatus,
    requirement_matches: list[dict],
) -> Evaluation:
    evaluation = Evaluation(
        resume_id=resume_id,
        jd_id=jd_id,
        overall_score=overall_score,
        deterministic_component=deterministic_component,
        llm_component=llm_component,
        confidence=confidence,
        ai_summary=ai_summary,
        strengths=strengths,
        gaps=gaps,
        interview_focus_areas=interview_focus_areas,
        llm_status=llm_status,
    )
    for m in requirement_matches:
        evaluation.requirement_matches.append(RequirementMatch(**m))

    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation
