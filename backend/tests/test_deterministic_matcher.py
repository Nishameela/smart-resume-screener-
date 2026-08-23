from app.services.deterministic_matcher import (
    EducationInput,
    ExperienceInput,
    evaluate_requirement,
    match_education_requirement,
    match_experience_requirement,
    match_responsibility_requirement,
    match_skill_requirement,
)
from app.services.skill_normalizer import default_normalizer

# --- Skill requirements ---


def test_skill_requirement_strong_match_via_exact():
    skills = default_normalizer.normalize_many(["Python", "FastAPI"])
    result = match_skill_requirement("Must have Python experience", skills)
    assert result.matched is True
    assert result.score == 100.0
    assert "Python" in result.summary


def test_skill_requirement_strong_match_via_normalized_alias():
    skills = default_normalizer.normalize_many(["ReactJS"])
    result = match_skill_requirement("Experience with React required", skills)
    assert result.matched is True
    assert result.score == 100.0
    assert "normalized match" in result.summary


def test_skill_requirement_missing_skill():
    skills = default_normalizer.normalize_many(["Java"])
    result = match_skill_requirement("Must have Python experience", skills)
    assert result.matched is False
    assert result.score == 0.0


def test_skill_requirement_short_skill_name_no_false_positive():
    """'Go' (a known canonical skill) must not spuriously match substrings
    inside unrelated words like 'Google' or 'good'."""
    skills = default_normalizer.normalize_many(["JavaScript"])
    result = match_skill_requirement(
        "Experience with Google search and good communication skills", skills
    )
    # No real taxonomy skill is referenced here and there's no literal
    # overlap with the candidate's skills either, so there must be no signal
    # (in particular, no false "Go" match and no false "R" match from "search").
    assert result.score is None
    assert result.matched is False


def test_skill_requirement_no_recognized_skill_falls_back_to_literal_overlap():
    skills = default_normalizer.normalize_many(["Figma"])
    result = match_skill_requirement("Experience with Figma for design", skills)
    assert result.matched is True
    assert result.score == 60.0
    assert "weaker evidence" in result.summary


def test_skill_requirement_no_signal_when_nothing_recognized_or_overlapping():
    skills = default_normalizer.normalize_many(["Python"])
    result = match_skill_requirement("Excellent communication and teamwork", skills)
    assert result.score is None
    assert result.matched is False


# --- Experience requirements ---


def test_experience_requirement_met():
    entries = [
        ExperienceInput(
            title="Engineer", company="Acme", start_date="2019", end_date=None, is_current=True
        )
    ]
    result = match_experience_requirement("3+ years of experience required", entries, current_year=2026)
    assert result.matched is True
    assert result.score == 100.0


def test_experience_requirement_not_met_partial_score():
    entries = [
        ExperienceInput(
            title="Intern", company="Acme", start_date="2025", end_date="2026", is_current=False
        )
    ]
    result = match_experience_requirement("5+ years of experience required", entries, current_year=2026)
    assert result.matched is False
    assert 0 < result.score < 100


def test_experience_requirement_zero_entries():
    result = match_experience_requirement("3+ years required", [], current_year=2026)
    assert result.matched is False
    assert result.score == 0.0


def test_experience_requirement_no_years_figure_has_no_signal():
    entries = [
        ExperienceInput(
            title="Engineer", company="Acme", start_date="2019", end_date=None, is_current=True
        )
    ]
    result = match_experience_requirement("Strong backend experience", entries, current_year=2026)
    assert result.score is None


def test_experience_requirement_sums_multiple_entries():
    entries = [
        ExperienceInput(title="A", company="X", start_date="2018", end_date="2020", is_current=False),
        ExperienceInput(title="B", company="Y", start_date="2020", end_date=None, is_current=True),
    ]
    result = match_experience_requirement("4+ years required", entries, current_year=2026)
    # (2020-2018) + (2026-2020) = 2 + 6 = 8 years >= 4
    assert result.matched is True


# --- Education requirements ---


def test_education_requirement_met_exact_level():
    entries = [
        EducationInput(
            degree="B.S. Computer Science",
            institution="State University",
            field_of_study="Computer Science",
            graduation_year="2021",
        )
    ]
    result = match_education_requirement("Bachelor's degree required", entries)
    assert result.matched is True
    assert result.score == 100.0


def test_education_requirement_met_by_higher_level():
    entries = [
        EducationInput(
            degree="M.S. Computer Science", institution="MIT", field_of_study="CS", graduation_year="2022"
        )
    ]
    result = match_education_requirement("Bachelor's degree required", entries)
    assert result.matched is True  # Master's satisfies a Bachelor's requirement


def test_education_requirement_not_met_lower_level():
    entries = [
        EducationInput(
            degree="Associate's Degree", institution="Community College", field_of_study=None, graduation_year=None
        )
    ]
    result = match_education_requirement("Master's degree required", entries)
    assert result.matched is False
    assert result.score == 0.0


def test_education_requirement_no_entries():
    result = match_education_requirement("Bachelor's degree required", [])
    assert result.matched is False
    assert result.score == 0.0


def test_education_requirement_no_level_detected_has_no_signal():
    entries = [EducationInput(degree="B.S.", institution="X", field_of_study=None, graduation_year=None)]
    result = match_education_requirement("Strong academic background", entries)
    assert result.score is None


# --- Responsibility requirements ---


def test_responsibility_requirement_always_has_no_deterministic_signal():
    result = match_responsibility_requirement("Collaborate with cross-functional teams")
    assert result.score is None
    assert result.matched is False


# --- Dispatcher ---


def test_evaluate_requirement_dispatches_by_category():
    skills = default_normalizer.normalize_many(["Python"])
    result = evaluate_requirement(
        "Must have Python experience",
        "skill",
        resume_skills=skills,
        experience_entries=[],
        education_entries=[],
    )
    assert result.category == "skill"
    assert result.matched is True
