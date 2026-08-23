"""
Deterministic (non-LLM) evidence layer: for one JD requirement, compute
whatever hard, rule-based signal is available from the candidate's
structured resume data -- skill overlap, years of experience, degree
level. This is the "structured/deterministic matching" half of the
hybrid engine (see README architecture section).

Pure functions operating on plain dataclasses (not ORM objects), so
this entire module is testable with zero database/LLM dependency and
runs in microseconds. Its output feeds the grounded LLM evaluation
stage (app/services/llm_evaluator.py) as factual context -- the LLM's
job there is to confirm/extend this evidence with semantic reasoning,
not to re-derive it from scratch.

Not every requirement category has a deterministic signal available
(e.g. a soft "responsibility" requirement like "work in a fast-paced
team"); in that case `score` is None rather than a fabricated number,
which the scorer (app/services/scorer.py) and the LLM prompt both
treat as "defer entirely to semantic judgment".
"""
import re
from dataclasses import dataclass
from datetime import datetime

from app.services.skill_normalizer import NormalizedSkill
from app.services.skill_taxonomy import SKILL_ALIASES


@dataclass(frozen=True)
class ExperienceInput:
    title: str | None
    company: str | None
    start_date: str | None
    end_date: str | None
    is_current: bool


@dataclass(frozen=True)
class EducationInput:
    degree: str | None
    institution: str | None
    field_of_study: str | None
    graduation_year: str | None


@dataclass(frozen=True)
class DeterministicEvidence:
    category: str
    matched: bool
    score: float | None  # 0-100, or None if no deterministic signal exists for this requirement
    summary: str  # human-readable evidence, fed to the LLM as grounding context


def _mentions_term(haystack_lower: str, term_lower: str) -> bool:
    """Whole-term containment check (not naive substring) so short terms
    like "Go", "R", "C#" don't spuriously match inside unrelated words."""
    if not term_lower:
        return False
    pattern = r"(?<![A-Za-z0-9])" + re.escape(term_lower) + r"(?![A-Za-z0-9])"
    return re.search(pattern, haystack_lower) is not None


# --- Skill requirements ---------------------------------------------------


def match_skill_requirement(
    requirement_text: str, resume_skills: list[NormalizedSkill]
) -> DeterministicEvidence:
    req_lower = requirement_text.lower()
    resume_by_canonical: dict[str, NormalizedSkill] = {s.canonical_name: s for s in resume_skills}

    referenced_skills = [
        canonical
        for canonical, aliases in SKILL_ALIASES.items()
        if any(_mentions_term(req_lower, term.lower()) for term in [canonical, *aliases])
    ]

    if referenced_skills:
        matched = [name for name in referenced_skills if name in resume_by_canonical]
        if matched:
            details = "; ".join(
                f"{name} ({resume_by_canonical[name].match_type.value} match: "
                f"candidate listed '{resume_by_canonical[name].raw_text}')"
                for name in matched
            )
            return DeterministicEvidence(
                category="skill",
                matched=True,
                score=100.0,
                summary=f"Deterministic skill check found: {details}.",
            )
        return DeterministicEvidence(
            category="skill",
            matched=False,
            score=0.0,
            summary=(
                f"Deterministic skill check: requirement references "
                f"{', '.join(referenced_skills)}, but no matching skill (exact or "
                f"normalized) was found among the candidate's extracted skills."
            ),
        )

    # Taxonomy didn't recognize a skill name in the requirement text. Fall
    # back to a literal text-overlap check, explicitly labeled as weaker
    # evidence than a taxonomy-based match.
    overlap = [s.raw_text for s in resume_skills if _mentions_term(req_lower, s.raw_text.lower())]
    if overlap:
        return DeterministicEvidence(
            category="skill",
            matched=True,
            score=60.0,
            summary=(
                f"No known skill name was recognized in this requirement by the "
                f"normalization taxonomy; a literal text overlap was found with "
                f"candidate skill(s) {overlap}. This is weaker evidence than a "
                f"taxonomy-based match and should be confirmed semantically."
            ),
        )
    return DeterministicEvidence(
        category="skill",
        matched=False,
        score=None,
        summary=(
            "No skill name recognized in this requirement by the normalization "
            "taxonomy, and no literal text overlap with the candidate's extracted "
            "skills. Deterministic layer has no signal for this requirement."
        ),
    )


# --- Experience requirements ------------------------------------------------

_YEARS_REQUIRED_PATTERN = re.compile(r"(\d+)\s*\+?\s*(?:-\s*\d+\s*)?\s*years?", re.IGNORECASE)
_FOUR_DIGIT_YEAR_PATTERN = re.compile(r"(19|20)\d{2}")


def _extract_year(text: str | None) -> int | None:
    if not text:
        return None
    match = _FOUR_DIGIT_YEAR_PATTERN.search(text)
    return int(match.group(0)) if match else None


def _compute_total_experience_years(entries: list[ExperienceInput], current_year: int) -> float:
    """Best-effort estimate from resume-stated dates. Overlapping/concurrent
    roles are summed rather than merged -- a documented approximation, not
    a claim of precision (see README limitations)."""
    total = 0.0
    for entry in entries:
        start_year = _extract_year(entry.start_date)
        if start_year is None:
            continue
        is_ongoing = entry.is_current or (
            entry.end_date is not None and re.search(r"present|current", entry.end_date, re.IGNORECASE)
        )
        end_year = current_year if is_ongoing else (_extract_year(entry.end_date) or current_year)
        total += max(0.0, end_year - start_year)
    return total


def match_experience_requirement(
    requirement_text: str,
    experience_entries: list[ExperienceInput],
    current_year: int | None = None,
) -> DeterministicEvidence:
    current_year = current_year or datetime.utcnow().year
    match = _YEARS_REQUIRED_PATTERN.search(requirement_text)
    if not match:
        return DeterministicEvidence(
            category="experience",
            matched=False,
            score=None,
            summary=(
                "No explicit years-of-experience figure detected in this requirement; "
                "deterministic layer has no numeric signal for this requirement."
            ),
        )

    required_years = int(match.group(1))
    candidate_years = _compute_total_experience_years(experience_entries, current_year)
    matched = required_years == 0 or candidate_years >= required_years
    score = 100.0 if matched else round(min(99.0, (candidate_years / required_years) * 100), 1)

    return DeterministicEvidence(
        category="experience",
        matched=matched,
        score=score,
        summary=(
            f"Deterministic experience check: requirement asks for {required_years}+ "
            f"years; candidate's resume dates sum to approximately "
            f"{candidate_years:.1f} years across {len(experience_entries)} entries."
        ),
    )


# --- Education requirements -------------------------------------------------

_DEGREE_LEVEL_SYNONYMS: dict[str, list[str]] = {
    "associate": ["associate", "a.a.", "a.s."],
    "bachelor": ["bachelor", "b.s.", "b.a.", "b.tech", "btech", "undergraduate"],
    "master": ["master", "m.s.", "m.a.", "mba", "m.tech", "mtech"],
    "doctorate": ["phd", "ph.d", "doctorate", "doctoral"],
}
_DEGREE_LEVEL_RANK = {"associate": 1, "bachelor": 2, "master": 3, "doctorate": 4}


def _degree_level(text: str | None) -> str | None:
    if not text:
        return None
    lower = text.lower()
    for level, synonyms in _DEGREE_LEVEL_SYNONYMS.items():
        if any(syn in lower for syn in synonyms):
            return level
    return None


def match_education_requirement(
    requirement_text: str, education_entries: list[EducationInput]
) -> DeterministicEvidence:
    required_level = _degree_level(requirement_text)
    if required_level is None:
        return DeterministicEvidence(
            category="education",
            matched=False,
            score=None,
            summary=(
                "No recognizable degree level found in this requirement; "
                "deterministic layer has no signal for this requirement."
            ),
        )

    for entry in education_entries:
        candidate_level = _degree_level(entry.degree)
        if candidate_level and _DEGREE_LEVEL_RANK[candidate_level] >= _DEGREE_LEVEL_RANK[required_level]:
            return DeterministicEvidence(
                category="education",
                matched=True,
                score=100.0,
                summary=(
                    f"Deterministic education check: requirement asks for at least a "
                    f"{required_level}'s degree; candidate has '{entry.degree}' from "
                    f"{entry.institution or 'an unspecified institution'}, which meets "
                    f"or exceeds that level."
                ),
            )

    degrees_on_file = [e.degree for e in education_entries if e.degree] or ["none"]
    return DeterministicEvidence(
        category="education",
        matched=False,
        score=0.0,
        summary=(
            f"Deterministic education check: requirement asks for at least a "
            f"{required_level}'s degree; no candidate education entry meets that "
            f"level. Candidate education on file: {degrees_on_file}."
        ),
    )


# --- Responsibility requirements (no deterministic signal) -----------------


def match_responsibility_requirement(requirement_text: str) -> DeterministicEvidence:
    return DeterministicEvidence(
        category="responsibility",
        matched=False,
        score=None,
        summary=(
            "This is a responsibility/soft requirement with no deterministic signal "
            "available; relies entirely on semantic judgment grounded in the resume text."
        ),
    )


# --- Dispatcher --------------------------------------------------------------


def evaluate_requirement(
    requirement_text: str,
    category: str,
    *,
    resume_skills: list[NormalizedSkill],
    experience_entries: list[ExperienceInput],
    education_entries: list[EducationInput],
    current_year: int | None = None,
) -> DeterministicEvidence:
    if category == "skill":
        return match_skill_requirement(requirement_text, resume_skills)
    if category == "experience":
        return match_experience_requirement(requirement_text, experience_entries, current_year)
    if category == "education":
        return match_education_requirement(requirement_text, education_entries)
    return match_responsibility_requirement(requirement_text)
