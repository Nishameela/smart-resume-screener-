"""LLM I/O schema for Prompt A (resume -> structured profile). Kept
separate from app/schemas/resume.py, which describes the API's
*outbound* representation of a persisted resume -- these two shapes
are related but not identical (this one is what we ask the model for
and validate against; that one is what we return to the frontend)."""
from pydantic import BaseModel, Field


class ExtractedSkillLLM(BaseModel):
    name: str = Field(
        description=(
            "A single skill, technology, tool, or certification exactly as named or "
            "clearly identifiable in the resume, e.g. 'Python', 'AWS', "
            "'AWS Certified Solutions Architect'."
        )
    )
    category: str | None = Field(
        default=None,
        description=(
            "A short category label, e.g. 'language', 'framework', 'database', 'cloud', "
            "'tool', 'certification', 'soft_skill'. Best guess is fine; null if unclear."
        ),
    )


class ExtractedExperienceLLM(BaseModel):
    title: str | None = Field(default=None, description="Job title as stated.")
    company: str | None = Field(default=None, description="Employer/organization name as stated.")
    start_date: str | None = Field(
        default=None, description="As stated in the resume, e.g. 'Jan 2021' or '2021'."
    )
    end_date: str | None = Field(
        default=None, description="As stated, or 'Present' if currently employed there."
    )
    is_current: bool = Field(
        default=False, description="True only if the resume explicitly indicates this is current."
    )
    description: str | None = Field(
        default=None,
        description=(
            "A concise summary (1-3 sentences) of responsibilities/achievements in this "
            "role, based only on what the resume actually states."
        ),
    )


class ExtractedEducationLLM(BaseModel):
    degree: str | None = Field(default=None, description="Degree name as stated, e.g. 'B.S.'.")
    institution: str | None = Field(default=None, description="School/university name as stated.")
    field_of_study: str | None = Field(default=None, description="Major/field, if stated.")
    graduation_year: str | None = Field(default=None, description="Graduation year, if stated.")


class ResumeExtractionResult(BaseModel):
    candidate_name: str | None = Field(
        default=None, description="Candidate's full name as it appears on the resume."
    )
    candidate_email: str | None = Field(
        default=None, description="Candidate's email address as it appears on the resume."
    )
    skills: list[ExtractedSkillLLM] = Field(
        description=(
            "Every distinct skill, technology, tool, or certification explicitly "
            "mentioned anywhere in the resume. Do not infer skills that are not stated. "
            "Do not duplicate the same skill under different casing."
        )
    )
    experience: list[ExtractedExperienceLLM] = Field(
        description="Each distinct work experience or internship entry in the resume."
    )
    education: list[ExtractedEducationLLM] = Field(
        description="Each distinct education entry in the resume."
    )
