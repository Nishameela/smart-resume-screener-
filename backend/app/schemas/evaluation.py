from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvaluationCreate(BaseModel):
    resume_id: int
    jd_id: int


class RequirementMatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requirement_text: str
    priority: str
    category: str
    match_level: str
    evidence: list[str]
    reasoning: str
    confidence: float

    @classmethod
    def from_orm_match(cls, match) -> "RequirementMatchOut":
        return cls(
            requirement_text=match.requirement.requirement_text,
            priority=match.requirement.priority.value,
            category=match.requirement.category.value,
            match_level=match.match_level.value,
            evidence=match.evidence,
            reasoning=match.reasoning,
            confidence=match.confidence,
        )


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resume_id: int
    jd_id: int
    overall_score: float
    deterministic_component: float | None
    llm_component: float
    confidence: float
    ai_summary: str | None
    strengths: list[str]
    gaps: list[str]
    interview_focus_areas: list[str]
    llm_status: str
    created_at: datetime
    requirement_matches: list[RequirementMatchOut]

    @classmethod
    def from_orm_evaluation(cls, evaluation) -> "EvaluationOut":
        return cls(
            id=evaluation.id,
            resume_id=evaluation.resume_id,
            jd_id=evaluation.jd_id,
            overall_score=evaluation.overall_score,
            deterministic_component=evaluation.deterministic_component,
            llm_component=evaluation.llm_component,
            confidence=evaluation.confidence,
            ai_summary=evaluation.ai_summary,
            strengths=evaluation.strengths,
            gaps=evaluation.gaps,
            interview_focus_areas=evaluation.interview_focus_areas,
            llm_status=evaluation.llm_status.value,
            created_at=evaluation.created_at,
            requirement_matches=[
                RequirementMatchOut.from_orm_match(m) for m in evaluation.requirement_matches
            ],
        )


class EvaluationSummaryOut(BaseModel):
    """Lighter payload for the ranking list -- one row per candidate."""

    id: int
    resume_id: int
    candidate_name: str | None
    filename: str
    overall_score: float
    confidence: float
    llm_status: str
    top_strength: str | None
    biggest_gap: str | None
    created_at: datetime

    @classmethod
    def from_orm_evaluation(cls, evaluation) -> "EvaluationSummaryOut":
        resume = evaluation.resume
        return cls(
            id=evaluation.id,
            resume_id=evaluation.resume_id,
            candidate_name=resume.candidate_name,
            filename=resume.filename,
            overall_score=evaluation.overall_score,
            confidence=evaluation.confidence,
            llm_status=evaluation.llm_status.value,
            top_strength=evaluation.strengths[0] if evaluation.strengths else None,
            biggest_gap=evaluation.gaps[0] if evaluation.gaps else None,
            created_at=evaluation.created_at,
        )
