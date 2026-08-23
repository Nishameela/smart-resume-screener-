from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import RequirementCategory, RequirementPriority


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_text: Mapped[str] = mapped_column(Text)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    requirements: Mapped[list["JDRequirement"]] = relationship(
        back_populates="job_description", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="job_description")


class JDRequirement(Base):
    __tablename__ = "jd_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jd_id: Mapped[int] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"))

    requirement_text: Mapped[str] = mapped_column(Text)
    priority: Mapped[RequirementPriority] = mapped_column(
        SAEnum(RequirementPriority, native_enum=False)
    )
    category: Mapped[RequirementCategory] = mapped_column(
        SAEnum(RequirementCategory, native_enum=False)
    )

    job_description: Mapped["JobDescription"] = relationship(back_populates="requirements")
    matches: Mapped[list["RequirementMatch"]] = relationship(back_populates="requirement")
