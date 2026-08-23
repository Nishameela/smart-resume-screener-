"""
Orchestrates the grounded LLM requirement-evaluation stage: builds
deterministic evidence for every requirement (app/services/
deterministic_matcher.py), feeds it into the merged Prompt C+D as
context, and returns the LLM's validated structured judgment alongside
the deterministic evidence it was grounded with (the caller -- see
app/services/evaluation_service.py -- combines both into the final
per-requirement and evaluation-level scores via app/services/scorer.py).
"""
from dataclasses import dataclass

from app.core.config import settings
from app.core.llm_client import call_structured
from app.models.job_description import JDRequirement
from app.models.resume import EducationEntry, ExperienceEntry, ResumeSkill
from app.prompts.requirement_evaluation import (
    SYSTEM_PROMPT,
    TOOL_DESCRIPTION,
    TOOL_NAME,
    build_requirements_block,
    build_skills_summary,
    build_user_prompt,
)
from app.schemas.evaluation_llm import EvaluationLLMResult
from app.services.deterministic_matcher import (
    DeterministicEvidence,
    EducationInput,
    ExperienceInput,
    evaluate_requirement,
)
from app.services.skill_normalizer import NormalizedSkill


@dataclass(frozen=True)
class GroundedEvaluation:
    llm_result: EvaluationLLMResult
    deterministic_by_index: dict[int, DeterministicEvidence]
    requirement_by_index: dict[int, JDRequirement]


def _to_normalized_skills(resume_skills: list[ResumeSkill]) -> list[NormalizedSkill]:
    return [
        NormalizedSkill(raw_text=s.raw_text, canonical_name=s.canonical_name, match_type=s.match_type)
        for s in resume_skills
    ]


def _to_experience_inputs(entries: list[ExperienceEntry]) -> list[ExperienceInput]:
    return [
        ExperienceInput(
            title=e.title, company=e.company, start_date=e.start_date, end_date=e.end_date,
            is_current=e.is_current,
        )
        for e in entries
    ]


def _to_education_inputs(entries: list[EducationEntry]) -> list[EducationInput]:
    return [
        EducationInput(
            degree=e.degree, institution=e.institution, field_of_study=e.field_of_study,
            graduation_year=e.graduation_year,
        )
        for e in entries
    ]


def compute_deterministic_evidence(
    *,
    resume_skills: list[ResumeSkill],
    experience_entries: list[ExperienceEntry],
    education_entries: list[EducationEntry],
    requirements: list[JDRequirement],
) -> tuple[dict[int, DeterministicEvidence], dict[int, JDRequirement]]:
    """Shared by the happy path (as LLM grounding context) and by the
    LLM-failure fallback path (app/services/evaluation_service.py), so
    the deterministic-only score computed there is exactly the same
    evidence the LLM would have been grounded with -- no drift between
    the two."""
    normalized_skills = _to_normalized_skills(resume_skills)
    experience_inputs = _to_experience_inputs(experience_entries)
    education_inputs = _to_education_inputs(education_entries)

    deterministic_by_index: dict[int, DeterministicEvidence] = {}
    requirement_by_index: dict[int, JDRequirement] = {}

    for i, req in enumerate(requirements, start=1):
        evidence = evaluate_requirement(
            req.requirement_text,
            req.category.value if hasattr(req.category, "value") else req.category,
            resume_skills=normalized_skills,
            experience_entries=experience_inputs,
            education_entries=education_inputs,
        )
        deterministic_by_index[i] = evidence
        requirement_by_index[i] = req

    return deterministic_by_index, requirement_by_index


def run_grounded_evaluation(
    *,
    resume_text: str,
    resume_skills: list[ResumeSkill],
    experience_entries: list[ExperienceEntry],
    education_entries: list[EducationEntry],
    requirements: list[JDRequirement],
) -> GroundedEvaluation:
    deterministic_by_index, requirement_by_index = compute_deterministic_evidence(
        resume_skills=resume_skills,
        experience_entries=experience_entries,
        education_entries=education_entries,
        requirements=requirements,
    )

    prompt_requirements = [
        {
            "index": i,
            "text": req.requirement_text,
            "priority": req.priority.value if hasattr(req.priority, "value") else req.priority,
            "category": req.category.value if hasattr(req.category, "value") else req.category,
            "deterministic_summary": deterministic_by_index[i].summary,
        }
        for i, req in requirement_by_index.items()
    ]

    normalized_skills = _to_normalized_skills(resume_skills)
    skills_summary = build_skills_summary(
        [
            {"raw_text": s.raw_text, "canonical_name": s.canonical_name, "match_type": s.match_type.value}
            for s in normalized_skills
        ]
    )
    requirements_block = build_requirements_block(prompt_requirements)
    user_prompt = build_user_prompt(
        resume_text=resume_text,
        candidate_skills_summary=skills_summary,
        requirements_block=requirements_block,
    )

    llm_result = call_structured(
        model=settings.model_for_evaluation,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        tool_name=TOOL_NAME,
        tool_description=TOOL_DESCRIPTION,
        input_schema=EvaluationLLMResult.model_json_schema(),
        response_model=EvaluationLLMResult,
        max_tokens=8192,
    )

    return GroundedEvaluation(
        llm_result=llm_result,
        deterministic_by_index=deterministic_by_index,
        requirement_by_index=requirement_by_index,
    )
