"""
Every tunable constant the scoring engine uses, in one place, per an
explicit product decision: weights and penalties get tuned *after*
seeing real results on the demo dataset (strong / partial / keyword-
trap / transferable-match candidates), not hardcoded scattered through
the codebase. Changing candidate rankings should mean editing numbers
here, never hunting through app/services/scorer.py.

See README "Matching/Scoring Methodology" for the documented formula
these constants plug into.
"""

# Per-requirement base score by the LLM's grounded match_level judgment.
MATCH_LEVEL_SCORES: dict[str, float] = {
    "strong": 100.0,
    "partial": 60.0,
    "weak": 30.0,
    "not_demonstrated": 0.0,
}

# How much each requirement counts toward the weighted average, by
# priority. A must-have counts twice as much as a preferred requirement.
REQUIREMENT_WEIGHTS: dict[str, float] = {
    "must_have": 2.0,
    "preferred": 1.0,
}

# Missing a must-have requirement entirely (match_level == not_demonstrated)
# subtracts this many points from the overall score, on top of the
# weighting above -- operationalizes "missing a critical requirement
# should matter more than missing a preferred one." Capped so a resume
# with many missing must-haves doesn't go needlessly negative before
# clamping (the weighted average already drives it toward 0).
MISSING_MUST_HAVE_PENALTY_PER_REQUIREMENT = 10.0
MISSING_MUST_HAVE_PENALTY_CAP = 40.0
