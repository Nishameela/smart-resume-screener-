"""LLM I/O schema for the merged Prompt C+D (per-requirement evidence
evaluation + overall candidate summary), returned in a single call."""
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RequirementMatchLLM(BaseModel):
    requirement_index: int = Field(
        description="The 1-based index of the requirement being evaluated, matching the order it was given in the prompt."
    )
    match_level: Literal["strong", "partial", "weak", "not_demonstrated"] = Field(
        description=(
            "strong = clear, direct evidence of this requirement in the resume; "
            "partial = some relevant but incomplete or indirect evidence; "
            "weak = only marginal/tangential relevance; "
            "not_demonstrated = no supporting evidence in the resume at all."
        )
    )
    evidence: list[str] = Field(
        default_factory=list,
        description=(
            "0-3 short quotes or close paraphrases taken directly from the resume text "
            "that support this match_level. Must be empty if match_level is "
            "not_demonstrated. Never fabricate a quote that isn't actually in the resume."
        ),
    )
    reasoning: str = Field(
        description="1-2 concise sentences explaining the judgment, in plain language a recruiter would read."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="How confident you are in this judgment, 0.0-1.0.")

    @model_validator(mode="after")
    def _enforce_evidence_shape(self) -> "RequirementMatchLLM":
        """The prompt asks for "0-3 quotes, empty if not_demonstrated," but
        that's advisory text the model can drift from -- until now nothing
        in code actually enforced it, which is exactly the kind of gap a
        project built around "never fabricate evidence" shouldn't have.
        Auto-correct rather than raise: a model that includes a quote
        alongside not_demonstrated (or returns >3 quotes) is very unlikely
        to be fabricating maliciously, just slightly off-instruction, so
        silently normalizing here is safer than spending a corrective-retry
        API call on it."""
        if self.match_level == "not_demonstrated":
            self.evidence = []
        elif len(self.evidence) > 3:
            self.evidence = self.evidence[:3]
        return self


class EvaluationSummaryLLM(BaseModel):
    strengths: list[str] = Field(
        default_factory=list,
        description="Up to 4 short bullet points on the candidate's strongest, best-evidenced qualifications for this specific role.",
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Up to 4 short bullet points on the most important missing or weakly-evidenced requirements, prioritizing must-have gaps.",
    )
    executive_summary: str = Field(
        description=(
            "2-3 sentences summarizing overall fit for this role. Use measured, "
            "non-decisive language such as 'a strong candidate for further review' -- "
            "never make an autonomous hiring decision like 'hire this candidate.'"
        )
    )
    interview_focus_areas: list[str] = Field(
        default_factory=list,
        description="Up to 3 specific topics an interviewer should probe given the gaps or uncertainties found.",
    )


class EvaluationLLMResult(BaseModel):
    requirement_matches: list[RequirementMatchLLM]
    summary: EvaluationSummaryLLM
