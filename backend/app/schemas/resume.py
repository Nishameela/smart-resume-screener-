from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProcessingStatus


class ExperienceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None
    company: str | None
    start_date: str | None
    end_date: str | None
    is_current: bool
    description: str | None


class EducationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    degree: str | None
    institution: str | None
    field_of_study: str | None
    graduation_year: str | None


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    raw_text: str
    canonical_name: str
    category: str | None
    match_type: str


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    candidate_name: str | None
    candidate_email: str | None
    processing_status: ProcessingStatus
    error_message: str | None
    created_at: datetime

    skills: list[SkillOut] = []
    experience_entries: list[ExperienceOut] = []
    education_entries: list[EducationOut] = []


class ResumeSummaryOut(BaseModel):
    """Lighter payload for list views (no raw text, no full child rows)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    candidate_name: str | None
    processing_status: ProcessingStatus
    created_at: datetime
