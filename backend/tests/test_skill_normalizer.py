from app.models.enums import SkillMatchType
from app.services.skill_normalizer import SkillNormalizer, default_normalizer, normalize_skill

# --- Exact matches ---


def test_exact_match_same_casing():
    result = normalize_skill("Python")
    assert result.match_type == SkillMatchType.EXACT
    assert result.canonical_name == "Python"


def test_exact_match_is_case_insensitive():
    result = normalize_skill("python")
    assert result.match_type == SkillMatchType.EXACT
    assert result.canonical_name == "Python"

    result = normalize_skill("PYTHON")
    assert result.match_type == SkillMatchType.EXACT
    assert result.canonical_name == "Python"


# --- Normalized (alias) matches ---


def test_normalized_alias_reactjs_to_react():
    result = normalize_skill("ReactJS")
    assert result.match_type == SkillMatchType.NORMALIZED
    assert result.canonical_name == "React"


def test_normalized_alias_js_to_javascript():
    result = normalize_skill("JS")
    assert result.match_type == SkillMatchType.NORMALIZED
    assert result.canonical_name == "JavaScript"


def test_normalized_alias_node_to_nodejs():
    result = normalize_skill("node")
    assert result.match_type == SkillMatchType.NORMALIZED
    assert result.canonical_name == "Node.js"


def test_normalized_alias_postgres_to_postgresql():
    result = normalize_skill("Postgres")
    assert result.match_type == SkillMatchType.NORMALIZED
    assert result.canonical_name == "PostgreSQL"


def test_normalized_alias_is_case_insensitive():
    result = normalize_skill("REACTJS")
    assert result.match_type == SkillMatchType.NORMALIZED
    assert result.canonical_name == "React"


def test_normalized_alias_ts_to_typescript():
    result = normalize_skill("ts")
    assert result.match_type == SkillMatchType.NORMALIZED
    assert result.canonical_name == "TypeScript"


# --- Unmatched ---


def test_unmatched_skill_not_in_taxonomy():
    result = normalize_skill("Figma")
    assert result.match_type == SkillMatchType.UNMATCHED
    assert result.canonical_name == "Figma"  # kept as-is, not invented


def test_unmatched_preserves_original_casing_as_canonical():
    result = normalize_skill("Some Obscure Tool")
    assert result.match_type == SkillMatchType.UNMATCHED
    assert result.canonical_name == "Some Obscure Tool"


# --- Whitespace handling ---


def test_strips_surrounding_whitespace():
    result = normalize_skill("  Python  ")
    assert result.raw_text == "Python"
    assert result.match_type == SkillMatchType.EXACT


# --- Unsafe non-equivalence: related skills must NOT be treated as aliases ---


def test_tensorflow_is_not_normalized_to_machine_learning():
    """TensorFlow and Machine Learning are related but not equivalent --
    the deterministic normalizer must never conflate them. Any credit
    for that relationship belongs to the semantic LLM evaluation stage,
    not silent string normalization."""
    result = normalize_skill("TensorFlow")
    assert result.canonical_name != "Machine Learning"
    assert result.match_type == SkillMatchType.EXACT
    assert result.canonical_name == "TensorFlow"


def test_agile_is_not_normalized_to_scrum():
    result = normalize_skill("Agile")
    assert result.canonical_name == "Agile"
    result2 = normalize_skill("Scrum")
    assert result2.canonical_name == "Scrum"
    assert result.canonical_name != result2.canonical_name


# --- Batch + introspection ---


def test_normalize_many_preserves_order():
    results = default_normalizer.normalize_many(["Python", "ReactJS", "Figma"])
    assert [r.canonical_name for r in results] == ["Python", "React", "Figma"]
    assert [r.match_type for r in results] == [
        SkillMatchType.EXACT,
        SkillMatchType.NORMALIZED,
        SkillMatchType.UNMATCHED,
    ]


def test_custom_taxonomy_is_isolated_from_default():
    custom = SkillNormalizer({"Widget": ["widgy"]})
    result = custom.normalize("widgy")
    assert result.canonical_name == "Widget"
    assert result.match_type == SkillMatchType.NORMALIZED
    # default taxonomy is untouched
    assert normalize_skill("widgy").match_type == SkillMatchType.UNMATCHED


def test_canonical_names_covered_includes_known_skills():
    covered = default_normalizer.canonical_names_covered()
    assert "React" in covered
    assert "Python" in covered
    assert "Machine Learning" in covered
