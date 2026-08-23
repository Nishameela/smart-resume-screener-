import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.llm_client import call_structured
from app.models.enums import ProcessingStatus
from app.models.resume import Resume
from app.prompts.resume_extraction import SYSTEM_PROMPT, TOOL_DESCRIPTION, TOOL_NAME, build_user_prompt
from app.repositories import resume_repository
from app.schemas.resume_extraction import ResumeExtractionResult
from app.services.skill_normalizer import default_normalizer

logger = logging.getLogger(__name__)


def parse_resume(resume_text: str) -> ResumeExtractionResult:
    """LLM Prompt A: turn raw resume text into a structured candidate
    profile. Raises LLMError (via call_structured) if the model cannot
    produce valid output within the configured retry budget."""
    return call_structured(
        model=settings.model_for_extraction,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(resume_text),
        tool_name=TOOL_NAME,
        tool_description=TOOL_DESCRIPTION,
        input_schema=ResumeExtractionResult.model_json_schema(),
        response_model=ResumeExtractionResult,
    )


def run_structured_extraction(db: Session, resume: Resume) -> Resume:
    """Orchestrates Prompt A + persistence for one resume. Never raises:
    an LLM failure here should not take down a whole batch upload, so we
    catch it and persist a FAILED status with a clear error_message
    instead -- the resume's raw text remains available for the frontend
    to show, and reprocessing can be added later without a schema change.

    Each raw skill name the LLM extracts is immediately run through the
    deterministic skill normalizer (exact / normalized / unmatched
    against the curated alias taxonomy) before being persisted, so
    resume_skills.canonical_name and .match_type are correct from the
    moment a resume finishes processing.
    """
    try:
        extraction = parse_resume(resume.raw_text)
    except LLMError as exc:
        logger.warning("Structured extraction failed for resume %s: %s", resume.id, exc)
        return resume_repository.set_status(db, resume, ProcessingStatus.FAILED, str(exc))

    skills = [
        {
            "raw_text": normalized.raw_text,
            "canonical_name": normalized.canonical_name,
            "category": s.category,
            "match_type": normalized.match_type,
        }
        for s in extraction.skills
        for normalized in [default_normalizer.normalize(s.name)]
    ]
    experience = [
        {
            "title": e.title,
            "company": e.company,
            "start_date": e.start_date,
            "end_date": e.end_date,
            "is_current": e.is_current,
            "description": e.description,
        }
        for e in extraction.experience
    ]
    education = [
        {
            "degree": e.degree,
            "institution": e.institution,
            "field_of_study": e.field_of_study,
            "graduation_year": e.graduation_year,
        }
        for e in extraction.education
    ]

    resume = resume_repository.replace_structured_data(
        db,
        resume,
        candidate_name=extraction.candidate_name,
        candidate_email=extraction.candidate_email,
        skills=skills,
        experience=experience,
        education=education,
    )
    return resume_repository.set_status(db, resume, ProcessingStatus.COMPLETED)
