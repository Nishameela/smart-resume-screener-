from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JDRequirementLLM(BaseModel):
    """One structured requirement as extracted by the LLM. Doubles as
    both the tool-call input schema (via .model_json_schema()) and the
    validation target for the response -- one definition, no drift
    between what we ask the model for and what we accept."""

    requirement_text: str = Field(
        description=(
            "A single, specific, atomic requirement stated or clearly implied by the "
            "JD, e.g. '3+ years of Python backend development'."
        )
    )
    priority: Literal["must_have", "preferred"] = Field(
        description=(
            "must_have if the JD states or clearly implies this is mandatory; "
            "preferred if described as a nice-to-have, bonus, or plus."
        )
    )
    category: Literal["skill", "experience", "education", "responsibility"] = Field(
        description=(
            "skill = a specific technology/tool/language; experience = years or type "
            "of experience; education = degree/certification; responsibility = a job "
            "duty or soft requirement not tied to a specific skill."
        )
    )


class JDExtractionResult(BaseModel):
    job_title: str | None = Field(
        default=None, description="The job title stated in the JD, or null if absent."
    )
    requirements: list[JDRequirementLLM] = Field(
        description=(
            "Every distinct requirement found in the JD, each categorized and "
            "prioritized. No duplicates; do not invent requirements absent from the text."
        )
    )


class JDRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requirement_text: str
    priority: str
    category: str


class JobDescriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_title: str | None
    created_at: datetime
    requirements: list[JDRequirementOut] = []


class JobDescriptionCreate(BaseModel):
    raw_text: str = Field(min_length=20, max_length=20000)
