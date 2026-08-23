"""
Resume and its normalized child entities: experience, education, skills.

One resume = one candidate profile in this application (no separate
Candidate table -- a resume upload *is* the candidate-creation event,
so a distinct 1:1 Candidate entity would be pure over-normalization).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ProcessingStatus, SkillMatchType


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(20))  # "pdf" | "txt"
    raw_text: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    candidate_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    processing_status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus, native_enum=False), default=ProcessingStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    experience_entries: Mapped[list["ExperienceEntry"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    education_entries: Mapped[list["EducationEntry"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    skills: Mapped[list["ResumeSkill"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="resume")


class ExperienceEntry(Base):
    __tablename__ = "experience_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_current: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    resume: Mapped["Resume"] = relationship(back_populates="experience_entries")


class EducationEntry(Base):
    __tablename__ = "education_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))

    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(255), nullable=True)
    field_of_study: Mapped[str | None] = mapped_column(String(255), nullable=True)
    graduation_year: Mapped[str | None] = mapped_column(String(10), nullable=True)

    resume: Mapped["Resume"] = relationship(back_populates="education_entries")


class ResumeSkill(Base):
    __tablename__ = "resume_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"))

    raw_text: Mapped[str] = mapped_column(String(255))
    canonical_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    match_type: Mapped[SkillMatchType] = mapped_column(SAEnum(SkillMatchType, native_enum=False))

    resume: Mapped["Resume"] = relationship(back_populates="skills")
