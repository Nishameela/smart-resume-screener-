"""
Provider-agnostic wrapper around the configured LLM (Anthropic Claude or
Google Gemini, selected via LLM_PROVIDER). Every other module that needs
the LLM goes through `call_structured` here -- no other file imports
`anthropic` or `google.genai` directly. This keeps the "LLM integration
must be isolated" requirement real rather than aspirational, and gives us
exactly one place to change if we ever add or swap providers again.

Structured output strategy differs by provider, but the contract callers
see is identical:
  - Anthropic: force a single tool call whose `input_schema` *is* the JSON
    schema we want (`response_model.model_json_schema()`). Anthropic's
    tool-use mechanism guarantees the response is schema-shaped JSON.
  - Gemini: request native JSON-mode structured output via
    `response_mime_type="application/json"` + `response_json_schema=`
    the same Pydantic-derived JSON schema (response_json_schema, not the
    older response_schema field, because it accepts raw JSON Schema
    including the `$defs`/`$ref` our nested Pydantic models produce --
    verified directly against the installed google-genai SDK's own field
    definitions, not assumed from memory).
In both cases, Pydantic then does the final semantic validation (types,
required fields, enum membership) that getting schema-shaped JSON back
does not by itself guarantee -- this is the second validation layer the
architecture calls for, and it is provider-independent.

Failure handling (shared by both providers): a validation failure
triggers one corrective retry that tells the model exactly what was
wrong. Transient network/API failures (timeouts, rate limits, 5xx) get
exponential-backoff retries up to settings.llm_max_retries. Non-retryable
failures (bad request, auth, missing model) raise immediately. If every
attempt is exhausted, we raise LLMError -- callers decide whether to fail
the request or fall back to deterministic-only scoring. Provider SDKs
raise different exception types for the same logical failure (a timeout
looks different in `anthropic` vs `google.genai`), so each provider's
invoker normalizes its own exceptions into the two internal signals below
before the shared retry loop ever sees them.
"""
import json
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import LLMError

T = TypeVar("T", bound=BaseModel)


class _TransientProviderError(Exception):
    """Internal signal: worth retrying with backoff (timeout, rate limit,
    5xx / server-side transient failure). Never escapes this module."""


class _NonRetryableProviderError(Exception):
    """Internal signal: should become LLMError immediately -- retrying
    won't help (bad request, auth failure, unknown model, safety block,
    response missing the expected structured output). Never escapes this
    module."""


def call_structured(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    response_model: type[T],
    max_tokens: int = 4096,
) -> T:
    """Call the configured LLM provider and validate the result against
    `response_model`. Returns a validated instance of `response_model`, or
    raises LLMError if the model/API cannot produce valid output within
    the configured retry budget.

    `tool_name` / `tool_description` are used by the Anthropic path (they
    name and describe the forced tool call); Gemini's native JSON mode has
    no equivalent concept and ignores them -- the full task instructions
    already live in `system_prompt` / `user_prompt` for both providers, so
    nothing is lost."""
    if not settings.active_api_key:
        raise LLMError(
            f"{settings.active_api_key_env_var} is not configured. Set it in backend/.env "
            "(see .env.example) to enable AI-powered extraction and matching."
        )

    prompt_for_attempt = user_prompt
    last_error: Exception | None = None
    total_attempts = settings.llm_max_retries + 1

    for attempt in range(total_attempts):
        try:
            raw_output = _invoke_tool(
                model=model,
                system_prompt=system_prompt,
                user_prompt=prompt_for_attempt,
                tool_name=tool_name,
                tool_description=tool_description,
                input_schema=input_schema,
                max_tokens=max_tokens,
            )
        except _TransientProviderError as exc:
            last_error = exc
            if attempt < total_attempts - 1:
                time.sleep(min(2**attempt, 8))
            continue
        except _NonRetryableProviderError as exc:
            raise LLMError(str(exc)) from exc

        try:
            return response_model.model_validate(raw_output)
        except ValidationError as exc:
            last_error = exc
            prompt_for_attempt = (
                f"{user_prompt}\n\n"
                f"Your previous response failed schema validation with this error:\n"
                f"{exc}\n\n"
                f"Call the tool again with corrected output that strictly matches the schema."
            )
            continue

    raise LLMError(
        f"LLM call did not produce valid output after {total_attempts} attempt(s): {last_error}"
    )


def _invoke_tool(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    max_tokens: int,
) -> dict[str, Any]:
    """Dispatches to the configured provider. Both branches raise only
    `_TransientProviderError` / `_NonRetryableProviderError` (or return a
    plain dict) -- never a provider-specific SDK exception -- so the retry
    loop in call_structured stays provider-agnostic."""
    if settings.llm_provider == "gemini":
        return _invoke_gemini(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            input_schema=input_schema,
            max_tokens=max_tokens,
        )
    return _invoke_anthropic(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        tool_name=tool_name,
        tool_description=tool_description,
        input_schema=input_schema,
        max_tokens=max_tokens,
    )


# --- Anthropic ---------------------------------------------------------

_anthropic_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic

        _anthropic_client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
        )
    return _anthropic_client


def _invoke_anthropic(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    max_tokens: int,
) -> dict[str, Any]:
    import anthropic

    client = _get_anthropic_client()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[
                {
                    "name": tool_name,
                    "description": tool_description,
                    "input_schema": input_schema,
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )
    except (
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        anthropic.RateLimitError,
        anthropic.InternalServerError,
    ) as exc:
        raise _TransientProviderError(str(exc)) from exc
    except anthropic.APIStatusError as exc:
        # Non-retryable client errors (bad request, auth, etc.)
        raise _NonRetryableProviderError(f"Anthropic API rejected the request: {exc}") from exc

    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input

    raise _NonRetryableProviderError("Anthropic response did not include the expected structured tool call.")


# --- Gemini --------------------------------------------------------------

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        from google.genai import types as genai_types

        _gemini_client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=genai_types.HttpOptions(timeout=settings.llm_timeout_seconds * 1000),
        )
    return _gemini_client


def _invoke_gemini(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    input_schema: dict[str, Any],
    max_tokens: int,
) -> dict[str, Any]:
    import httpx
    from google.genai import errors as genai_errors
    from google.genai import types as genai_types

    client = _get_gemini_client()
    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_json_schema=input_schema,
                temperature=0,
                max_output_tokens=max_tokens,
            ),
        )
    except genai_errors.ServerError as exc:
        raise _TransientProviderError(str(exc)) from exc
    except genai_errors.ClientError as exc:
        if exc.code == 429:  # rate limit -- retryable
            raise _TransientProviderError(str(exc)) from exc
        raise _NonRetryableProviderError(f"Gemini API rejected the request: {exc}") from exc
    except httpx.HTTPError as exc:
        # Connection-level failures (timeout, DNS, reset) surface as raw
        # httpx errors rather than a google.genai.errors subclass -- the
        # SDK is built directly on httpx and doesn't wrap these itself.
        raise _TransientProviderError(str(exc)) from exc

    text = getattr(response, "text", None)
    if not text:
        block_reason = getattr(getattr(response, "prompt_feedback", None), "block_reason", None)
        raise _NonRetryableProviderError(
            f"Gemini returned no usable output (possible safety block; block_reason={block_reason})."
        )

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _NonRetryableProviderError(f"Gemini did not return valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise _NonRetryableProviderError(
            f"Gemini returned valid JSON but not a JSON object (got {type(parsed).__name__})."
        )
    return parsed
