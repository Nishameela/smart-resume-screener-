"""
Unit tests for the code-level backstop on RequirementMatchLLM's evidence
field (app/schemas/evaluation_llm.py) -- the "0-3 quotes, empty if
not_demonstrated" contract was previously enforced only by prompt text,
so a model that drifted from it would sail through Pydantic validation
unnoticed. These confirm the model_validator actually normalizes it.
"""
from app.schemas.evaluation_llm import RequirementMatchLLM


def _match(**overrides):
    fields = dict(
        requirement_index=1,
        match_level="strong",
        evidence=[],
        reasoning="test",
        confidence=0.9,
    )
    fields.update(overrides)
    return RequirementMatchLLM.model_validate(fields)


def test_evidence_is_cleared_when_not_demonstrated():
    result = _match(match_level="not_demonstrated", evidence=["a stray quote"])
    assert result.evidence == []


def test_evidence_over_three_items_is_truncated():
    result = _match(match_level="strong", evidence=["a", "b", "c", "d", "e"])
    assert result.evidence == ["a", "b", "c"]


def test_evidence_within_bounds_is_left_untouched():
    result = _match(match_level="partial", evidence=["one quote", "another quote"])
    assert result.evidence == ["one quote", "another quote"]


def test_empty_evidence_on_a_demonstrated_match_is_unaffected():
    result = _match(match_level="weak", evidence=[])
    assert result.evidence == []
