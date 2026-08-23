"""
Centralized application configuration.

All runtime-tunable values (LLM model selection, retry/timeout behavior,
database location, upload limits, CORS) live here and are sourced from
environment variables / a .env file. Nothing here should ever be
hardcoded elsewhere in the codebase -- if a module needs a tunable
value, it imports `settings` from this module.
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

# Built-in fallback model per provider, used only when LLM_MODEL_DEFAULT is
# left unset -- switching LLM_PROVIDER alone (without also touching
# LLM_MODEL_DEFAULT) should still produce a valid model name for the newly
# selected provider rather than silently sending e.g. "claude-sonnet-5" to
# Gemini. An explicit LLM_MODEL_DEFAULT in .env always wins over this.
_PROVIDER_FALLBACK_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-5",
    # gemini-2.5-flash was retired for new callers (confirmed via a live
    # 404 from the Gemini API itself, which named gemini-3.6-flash as the
    # replacement) -- if this trips again, LLM_MODEL_DEFAULT in .env can
    # override it without a code change.
    "gemini": "gemini-3.6-flash",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM provider selection ---
    # Which SDK/API call_structured() dispatches to. See app/core/llm_client.py
    # for the provider implementations; every other module stays unaware of
    # which provider is active and only ever calls call_structured().
    llm_provider: Literal["anthropic", "gemini"] = "gemini"

    # --- LLM: provider credentials ---
    anthropic_api_key: str = ""
    gemini_api_key: str = ""

    # --- LLM: model selection ---
    # Left empty by default so it doesn't silently pin every provider to an
    # Anthropic-shaped model name -- see _PROVIDER_FALLBACK_MODELS above.
    llm_model_default: str = ""
    llm_model_extraction: str | None = None
    llm_model_evaluation: str | None = None
    llm_max_retries: int = 2
    llm_timeout_seconds: int = 30

    # --- Database ---
    database_url: str = "sqlite:///./data/app.db"

    # --- Uploads ---
    max_upload_size_mb: int = 5

    # --- CORS --- (both "localhost" and "127.0.0.1" for Vite's dev/preview ports;
    # browsers treat these as distinct origins even when they resolve identically)
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )

    @property
    def resolved_default_model(self) -> str:
        """LLM_MODEL_DEFAULT if explicitly set, else the built-in fallback
        for whichever provider is active. Kept as one place so a bare
        `LLM_PROVIDER=gemini` switch (with no other .env changes) still
        resolves to a valid Gemini model name instead of an Anthropic one."""
        return self.llm_model_default or _PROVIDER_FALLBACK_MODELS[self.llm_provider]

    @property
    def model_for_extraction(self) -> str:
        return self.llm_model_extraction or self.resolved_default_model

    @property
    def model_for_evaluation(self) -> str:
        return self.llm_model_evaluation or self.resolved_default_model

    @property
    def active_api_key(self) -> str:
        """The credential for whichever provider LLM_PROVIDER selects --
        this is the single value app/core/llm_client.py checks before
        making a call, so it never has to branch on provider itself."""
        return self.gemini_api_key if self.llm_provider == "gemini" else self.anthropic_api_key

    @property
    def active_api_key_env_var(self) -> str:
        return "GEMINI_API_KEY" if self.llm_provider == "gemini" else "ANTHROPIC_API_KEY"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
