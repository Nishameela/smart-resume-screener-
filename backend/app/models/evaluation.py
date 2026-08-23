from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LLMStatus, MatchLevel


class Evaluation(Base):
    """One resume x one JD, scored. See app/core/scoring_config.py for the
    documented weighting/penalty formula that produces overall_score."""

    __tablename__ = "evaluations"
    __table_args__ = (
        # DB-level guarantee behind the service-layer idempotency check in
        # evaluation_service.get_or_create_evaluation -- prevents a race
        # between two concurrent requests for the same pair from both
        # passing the "does it already exist" read before either commits.
        UniqueConstraint("resume_id", "jd_id", name="uq_evaluation_resume_jd"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )
    jd_id: Mapped[int] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True
    )

    overall_score: Mapped[float] = mapped_column(Float)
    # Nullable, not defaulted to 0.0: None means "no requirement in this
    # evaluation had a deterministic signal at all" (e.g. an all-soft-skill
    # JD), which is meaningfully different from "the rule-based check
    # actively found nothing" (0.0).
    deterministic_component: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_component: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)

    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    gaps: Mapped[list] = mapped_column(JSON, default=list)
    interview_focus_areas: Mapped[list] = mapped_column(JSON, default=list)

    llm_status: Mapped[LLMStatus] = mapped_column(SAEnum(LLMStatus, native_enum=False))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    resume: Mapped["Resume"] = relationship(back_populates="evaluations")  # noqa: F821
    job_description: Mapped["JobDescription"] = relationship(  # noqa: F821
        back_populates="evaluations"
    )
    requirement_matches: Mapped[list["RequirementMatch"]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        # Rows are inserted in JD-requirement order (see evaluation_repository's
        # create path); without an explicit order_by, selectinload's read-back
        # order is not guaranteed, which would make the requirement-by-requirement
        # breakdown -- the app's signature explainability feature -- jump around
        # on every page load. Insertion order == id order here.
        order_by="RequirementMatch.id",
    )


class RequirementMatch(Base):
    """The core signature-feature record: one row per JD requirement per
    evaluation, carrying the evidence-based, human-readable explanation."""

    __tablename__ = "requirement_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluations.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[int] = mapped_column(
        ForeignKey("jd_requirements.id", ondelete="CASCADE")
    )

    match_level: Mapped[MatchLevel] = mapped_column(SAEnum(MatchLevel, native_enum=False))
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # list[str] quotes/snippets
    reasoning: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)

    evaluation: Mapped["Evaluation"] = relationship(back_populates="requirement_matches")
    requirement: Mapped["JDRequirement"] = relationship(back_populates="matches")  # noqa: F821
