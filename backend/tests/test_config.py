"""
Unit tests for the provider-selection logic in app/core/config.py --
specifically the computed properties that let LLM_PROVIDER switch between
Anthropic and Gemini without every other module needing to branch on which
provider is active. Constructs fresh Settings instances directly (bypassing
the process-wide .env-loaded singleton) so each case is isolated.
"""
from app.core.config import Settings


def test_gemini_is_the_default_provider():
    s = Settings(_env_file=None)
    assert s.llm_provider == "gemini"


def test_resolved_default_model_falls_back_per_provider_when_unset():
    anthropic_settings = Settings(_env_file=None, llm_provider="anthropic")
    gemini_settings = Settings(_env_file=None, llm_provider="gemini")

    assert anthropic_settings.resolved_default_model == "claude-sonnet-5"
    assert gemini_settings.resolved_default_model == "gemini-3.6-flash"


def test_explicit_llm_model_default_overrides_provider_fallback():
    s = Settings(_env_file=None, llm_provider="gemini", llm_model_default="gemini-2.0-flash")
    assert s.resolved_default_model == "gemini-2.0-flash"


def test_model_for_extraction_and_evaluation_prefer_stage_specific_override():
    s = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_model_default="gemini-2.5-flash",
        llm_model_extraction="gemini-2.5-flash-lite",
    )
    assert s.model_for_extraction == "gemini-2.5-flash-lite"
    assert s.model_for_evaluation == "gemini-2.5-flash"  # no override -> falls back to default


def test_active_api_key_selects_by_provider():
    s = Settings(
        _env_file=None,
        llm_provider="gemini",
        anthropic_api_key="anthropic-key",
        gemini_api_key="gemini-key",
    )
    assert s.active_api_key == "gemini-key"
    assert s.active_api_key_env_var == "GEMINI_API_KEY"

    s2 = Settings(
        _env_file=None,
        llm_provider="anthropic",
        anthropic_api_key="anthropic-key",
        gemini_api_key="gemini-key",
    )
    assert s2.active_api_key == "anthropic-key"
    assert s2.active_api_key_env_var == "ANTHROPIC_API_KEY"


def test_invalid_llm_provider_is_rejected_at_construction():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="openai")
