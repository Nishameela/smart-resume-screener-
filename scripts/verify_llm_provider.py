"""
Minimal real-call verification for the configured LLM provider. Run this
BEFORE trying the full app, so a config/auth/schema problem shows up in
one small call instead of buried inside a resume upload.

Usage (from backend/, with venv activated and .env configured):
    python ../scripts/verify_llm_provider.py

Exits 0 and prints "VERIFIED OK" on success; exits 1 with the raised
error otherwise. Never prints the API key itself.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from pydantic import BaseModel, Field  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.llm_client import call_structured  # noqa: E402
from app.core.exceptions import LLMError  # noqa: E402


class _CapitalCheck(BaseModel):
    country: str = Field(description="The country name, echoed back exactly as given.")
    capital_city: str = Field(description="The capital city of that country.")
    confidence: float = Field(description="0.0-1.0 confidence in this answer.")


def main() -> int:
    print(f"LLM_PROVIDER = {settings.llm_provider}")
    print(f"model        = {settings.resolved_default_model}")
    print(f"api key set  = {bool(settings.active_api_key)}  (env var: {settings.active_api_key_env_var})")

    if not settings.active_api_key:
        print(f"\nFAILED: {settings.active_api_key_env_var} is empty in backend/.env.")
        return 1

    print("\nCalling the LLM (this is a real, billed-or-free-tier API call)...")
    try:
        result = call_structured(
            model=settings.resolved_default_model,
            system_prompt="You answer geography questions with structured data. Be accurate.",
            user_prompt="What is the capital of France?",
            tool_name="capital_check",
            tool_description="Report the capital city of the given country.",
            input_schema=_CapitalCheck.model_json_schema(),
            response_model=_CapitalCheck,
            max_tokens=256,
        )
    except LLMError as exc:
        print(f"\nFAILED: {exc}")
        return 1

    print(f"\nParsed, Pydantic-validated result: {result.model_dump()}")
    if result.capital_city.strip().lower() != "paris":
        print(f"\nWARNING: expected 'Paris', got {result.capital_city!r} -- call succeeded but answer is wrong.")
        return 1

    print("\nVERIFIED OK -- structured output round-tripped through the real provider and validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
