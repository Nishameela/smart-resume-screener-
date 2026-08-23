"""
Pure aggregation logic: turns per-requirement match data into one
evaluation-level score. Reads its weights/penalty from
app/core/scoring_config.py -- nothing here is a hardcoded magic number,
so the formula can be tuned after seeing results on the demo dataset
without touching this logic.

Design (documented in the README "Matching/Scoring Methodology"
section): the deterministic matcher's evidence is fed INTO the grounded
LLM evaluation as context (see app/services/llm_evaluator.py), so the
LLM's per-requirement match_level is already evidence-informed -- it is
the authoritative per-requirement score, not a second number to
separately blend in. What *is* computed here as two parallel
evaluation-level components is for transparency: `deterministic_component`
shows what a pure rule-based system alone would have scored (ignoring
the LLM entirely, over only the requirements where a deterministic
signal existed), while `llm_component` is the grounded, LLM-informed
score that (after the missing-must-have penalty) becomes `overall_score`.
Showing both side by side in the UI is a legible way to demonstrate
exactly what the hybrid approach adds over pure keyword/rule matching.
"""
from dataclasses import dataclass

from app.core.scoring_config import (
    MATCH_LEVEL_SCORES,
    MISSING_MUST_HAVE_PENALTY_CAP,
    MISSING_MUST_HAVE_PENALTY_PER_REQUIREMENT,
    REQUIREMENT_WEIGHTS,
)


@dataclass(frozen=True)
class RequirementScoreInput:
    priority: str  # "must_have" | "preferred"
    match_level: str  # "strong" | "partial" | "weak" | "not_demonstrated"
    confidence: float
    deterministic_score: float | None  # None if the deterministic layer had no signal


@dataclass(frozen=True)
class ScoreBreakdown:
    overall_score: float
    llm_component: float
    deterministic_component: float | None
    confidence: float
    missing_must_have_count: int
    penalty_applied: float


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _weighted_average(pairs: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in pairs)
    if total_weight == 0:
        return 0.0
    return sum(value * weight for value, weight in pairs) / total_weight


def compute_score(requirements: list[RequirementScoreInput]) -> ScoreBreakdown:
    if not requirements:
        return ScoreBreakdown(
            overall_score=0.0,
            llm_component=0.0,
            deterministic_component=None,
            confidence=0.0,
            missing_must_have_count=0,
            penalty_applied=0.0,
        )

    llm_component = _weighted_average(
        [(MATCH_LEVEL_SCORES[r.match_level], REQUIREMENT_WEIGHTS[r.priority]) for r in requirements]
    )

    deterministic_pairs = [
        (r.deterministic_score, REQUIREMENT_WEIGHTS[r.priority])
        for r in requirements
        if r.deterministic_score is not None
    ]
    deterministic_component = _weighted_average(deterministic_pairs) if deterministic_pairs else None

    confidence = _weighted_average([(r.confidence, REQUIREMENT_WEIGHTS[r.priority]) for r in requirements])

    missing_must_have_count = sum(
        1
        for r in requirements
        if r.priority == "must_have" and r.match_level == "not_demonstrated"
    )
    penalty = min(
        MISSING_MUST_HAVE_PENALTY_CAP,
        MISSING_MUST_HAVE_PENALTY_PER_REQUIREMENT * missing_must_have_count,
    )

    overall_score = _clamp(llm_component - penalty)

    return ScoreBreakdown(
        overall_score=round(overall_score, 1),
        llm_component=round(llm_component, 1),
        deterministic_component=(
            round(deterministic_component, 1) if deterministic_component is not None else None
        ),
        confidence=round(confidence, 3),
        missing_must_have_count=missing_must_have_count,
        penalty_applied=round(penalty, 1),
    )
