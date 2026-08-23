from app.services.scorer import RequirementScoreInput, compute_score


def _req(priority="must_have", match_level="strong", confidence=0.9, deterministic_score=100.0):
    return RequirementScoreInput(
        priority=priority,
        match_level=match_level,
        confidence=confidence,
        deterministic_score=deterministic_score,
    )


def test_all_strong_must_haves_scores_near_100():
    reqs = [_req(match_level="strong") for _ in range(4)]
    result = compute_score(reqs)
    assert result.overall_score == 100.0
    assert result.missing_must_have_count == 0
    assert result.penalty_applied == 0.0


def test_all_not_demonstrated_scores_0():
    reqs = [_req(match_level="not_demonstrated", deterministic_score=0.0) for _ in range(3)]
    result = compute_score(reqs)
    assert result.overall_score == 0.0


def test_partial_match_scores_between_bounds():
    reqs = [_req(match_level="partial", deterministic_score=None)]
    result = compute_score(reqs)
    assert 0 < result.overall_score < 100
    assert result.overall_score == 60.0  # MATCH_LEVEL_SCORES["partial"], no penalty triggered


def test_missing_must_have_applies_penalty():
    # One strong must-have, one missing (not_demonstrated) must-have.
    reqs = [
        _req(priority="must_have", match_level="strong"),
        _req(priority="must_have", match_level="not_demonstrated", deterministic_score=0.0),
    ]
    result = compute_score(reqs)
    assert result.missing_must_have_count == 1
    assert result.penalty_applied == 10.0
    # weighted avg = (100*2 + 0*2) / 4 = 50; minus 10 penalty = 40
    assert result.overall_score == 40.0


def test_missing_preferred_does_not_trigger_penalty():
    reqs = [
        _req(priority="must_have", match_level="strong"),
        _req(priority="preferred", match_level="not_demonstrated", deterministic_score=0.0),
    ]
    result = compute_score(reqs)
    assert result.missing_must_have_count == 0
    assert result.penalty_applied == 0.0
    # weighted avg = (100*2 + 0*1) / 3 = 66.7
    assert result.overall_score == round(200 / 3, 1)


def test_penalty_is_capped_regardless_of_how_many_must_haves_are_missing():
    reqs = [_req(priority="must_have", match_level="not_demonstrated", deterministic_score=0.0) for _ in range(10)]
    result = compute_score(reqs)
    assert result.penalty_applied == 40.0  # capped, not 100.0
    assert result.overall_score == 0.0  # already 0 before penalty; clamped


def test_score_never_goes_below_zero():
    reqs = [_req(priority="must_have", match_level="not_demonstrated", deterministic_score=0.0) for _ in range(1)] + [
        _req(priority="must_have", match_level="weak", deterministic_score=0.0)
    ]
    result = compute_score(reqs)
    assert result.overall_score >= 0.0


def test_score_never_exceeds_100():
    reqs = [_req(match_level="strong") for _ in range(5)]
    result = compute_score(reqs)
    assert result.overall_score <= 100.0


def test_must_have_weighted_more_than_preferred():
    # Same match levels, but which one is must_have vs preferred flips the result.
    reqs_a = [
        _req(priority="must_have", match_level="strong"),
        _req(priority="preferred", match_level="weak"),
    ]
    reqs_b = [
        _req(priority="must_have", match_level="weak"),
        _req(priority="preferred", match_level="strong"),
    ]
    result_a = compute_score(reqs_a)
    result_b = compute_score(reqs_b)
    assert result_a.overall_score > result_b.overall_score


def test_deterministic_component_ignores_requirements_with_no_signal():
    reqs = [
        _req(match_level="strong", deterministic_score=100.0),
        _req(match_level="strong", deterministic_score=None),  # e.g. a responsibility requirement
    ]
    result = compute_score(reqs)
    assert result.deterministic_component == 100.0  # only the one with a signal counted


def test_deterministic_component_is_none_when_no_requirement_has_a_signal():
    reqs = [_req(match_level="strong", deterministic_score=None) for _ in range(2)]
    result = compute_score(reqs)
    assert result.deterministic_component is None


def test_empty_requirements_returns_zero_score_not_error():
    result = compute_score([])
    assert result.overall_score == 0.0
    assert result.deterministic_component is None


def test_confidence_is_weighted_average():
    reqs = [
        _req(priority="must_have", confidence=1.0),
        _req(priority="preferred", confidence=0.0),
    ]
    result = compute_score(reqs)
    # (1.0*2 + 0.0*1) / 3 = 0.667
    assert result.confidence == round(2 / 3, 3)


def test_keyword_trap_scores_lower_than_transferable_match_scenario():
    """Regression-style sanity check for the demo's core narrative: a
    candidate with many keyword hits but weak/no real evidence (few
    strong match levels, a missing must-have) should score lower than a
    candidate with fewer exact keywords but genuinely strong/partial
    evidence across the must-haves."""
    keyword_trap = [
        _req(priority="must_have", match_level="weak", deterministic_score=100.0),  # keyword present, but LLM found it's superficial
        _req(priority="must_have", match_level="not_demonstrated", deterministic_score=0.0),
        _req(priority="preferred", match_level="weak", deterministic_score=100.0),
    ]
    transferable = [
        _req(priority="must_have", match_level="strong", deterministic_score=None),
        _req(priority="must_have", match_level="partial", deterministic_score=None),
        _req(priority="preferred", match_level="partial", deterministic_score=None),
    ]
    trap_result = compute_score(keyword_trap)
    transferable_result = compute_score(transferable)
    assert transferable_result.overall_score > trap_result.overall_score
