"""
Unit tests for the LLM client wrapper using a mocked Anthropic SDK --
no real API key or network call required. Exercises the parts that
matter most for reliability: structured-output validation, the
corrective retry on malformed output, and graceful failure when the
API key is missing or the provider is persistently unavailable.
"""
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from app.core.exceptions import LLMError


class _DummySchema(BaseModel):
    value: str


def _tool_use_response(tool_name: str, input_dict: dict):
    block = SimpleNamespace(type="tool_use", name=tool_name, input=input_dict)
    return SimpleNamespace(content=[block])


def test_raises_llm_error_when_api_key_missing(monkeypatch):
    from app.core import llm_client

    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "")
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        llm_client.call_structured(
            model="claude-sonnet-5",
            system_prompt="sys",
            user_prompt="user",
            tool_name="t",
            tool_description="d",
            input_schema=_DummySchema.model_json_schema(),
            response_model=_DummySchema,
        )


def test_successful_structured_call(monkeypatch):
    from app.core import llm_client

    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "fake-key")

    with patch.object(llm_client, "_invoke_tool", return_value={"value": "hello"}) as mock_invoke:
        result = llm_client.call_structured(
            model="claude-sonnet-5",
            system_prompt="sys",
            user_prompt="user",
            tool_name="t",
            tool_description="d",
            input_schema=_DummySchema.model_json_schema(),
            response_model=_DummySchema,
        )
    assert result.value == "hello"
    assert mock_invoke.call_count == 1


def test_corrective_retry_on_invalid_output(monkeypatch):
    from app.core import llm_client

    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "fake-key")
    monkeypatch.setattr(llm_client.settings, "llm_max_retries", 1)

    calls = [{"wrong_field": 1}, {"value": "corrected"}]

    with patch.object(llm_client, "_invoke_tool", side_effect=calls) as mock_invoke:
        result = llm_client.call_structured(
            model="claude-sonnet-5",
            system_prompt="sys",
            user_prompt="user",
            tool_name="t",
            tool_description="d",
            input_schema=_DummySchema.model_json_schema(),
            response_model=_DummySchema,
        )
    assert result.value == "corrected"
    assert mock_invoke.call_count == 2


def test_raises_after_exhausting_retries_on_persistent_invalid_output(monkeypatch):
    from app.core import llm_client

    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "fake-key")
    monkeypatch.setattr(llm_client.settings, "llm_max_retries", 1)

    with patch.object(llm_client, "_invoke_tool", return_value={"wrong_field": 1}) as mock_invoke:
        with pytest.raises(LLMError, match="did not produce valid output"):
            llm_client.call_structured(
                model="claude-sonnet-5",
                system_prompt="sys",
                user_prompt="user",
                tool_name="t",
                tool_description="d",
                input_schema=_DummySchema.model_json_schema(),
                response_model=_DummySchema,
            )
    assert mock_invoke.call_count == 2  # initial + 1 retry


def test_retries_then_raises_on_persistent_transient_api_error(monkeypatch):
    """Generic retry-loop behavior: a provider invoker signaling a
    transient failure (regardless of which provider produced it) gets
    retried up to the configured budget, then raises LLMError. Provider-
    specific exception -> signal normalization is covered separately by
    test_invoke_anthropic_normalizes_timeout_to_transient_error and
    test_invoke_gemini_normalizes_errors below."""
    from app.core import llm_client

    monkeypatch.setattr(llm_client.settings, "anthropic_api_key", "fake-key")
    monkeypatch.setattr(llm_client.settings, "llm_max_retries", 1)
    monkeypatch.setattr(llm_client.time, "sleep", lambda *_: None)

    with patch.object(
        llm_client, "_invoke_tool", side_effect=llm_client._TransientProviderError("timed out")
    ) as mock_invoke:
        with pytest.raises(LLMError, match="did not produce valid output"):
            llm_client.call_structured(
                model="claude-sonnet-5",
                system_prompt="sys",
                user_prompt="user",
                tool_name="t",
                tool_description="d",
                input_schema=_DummySchema.model_json_schema(),
                response_model=_DummySchema,
            )
    assert mock_invoke.call_count == 2


def test_invoke_anthropic_normalizes_timeout_to_transient_error(monkeypatch):
    """Exercises the real exception-normalization code in _invoke_anthropic
    (not a mock standing in for it): the underlying SDK client raises
    anthropic.APITimeoutError, and _invoke_anthropic must convert that into
    the internal _TransientProviderError signal the retry loop understands."""
    from app.core import llm_client

    fake_client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **_: (_ for _ in ()).throw(anthropic.APITimeoutError(request=SimpleNamespace()))
        )
    )
    monkeypatch.setattr(llm_client, "_get_anthropic_client", lambda: fake_client)

    with pytest.raises(llm_client._TransientProviderError):
        llm_client._invoke_anthropic(
            model="claude-sonnet-5",
            system_prompt="sys",
            user_prompt="user",
            tool_name="t",
            tool_description="d",
            input_schema=_DummySchema.model_json_schema(),
            max_tokens=4096,
        )


def test_invoke_anthropic_normalizes_status_error_to_non_retryable(monkeypatch):
    from app.core import llm_client

    fake_response = httpx.Response(
        400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    status_error = anthropic.APIStatusError(
        message="bad request",
        response=fake_response,
        body={"error": {"message": "bad request"}},
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **_: (_ for _ in ()).throw(status_error))
    )
    monkeypatch.setattr(llm_client, "_get_anthropic_client", lambda: fake_client)

    with pytest.raises(llm_client._NonRetryableProviderError):
        llm_client._invoke_anthropic(
            model="claude-sonnet-5",
            system_prompt="sys",
            user_prompt="user",
            tool_name="t",
            tool_description="d",
            input_schema=_DummySchema.model_json_schema(),
            max_tokens=4096,
        )


# --- Gemini provider ------------------------------------------------------
#
# Mirrors the Anthropic tests above: mock at the SDK-client boundary
# (_get_gemini_client) so the real exception-normalization code in
# _invoke_gemini runs for real, no network call or API key required.


def test_raises_llm_error_when_gemini_api_key_missing(monkeypatch):
    from app.core import llm_client

    monkeypatch.setattr(llm_client.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_client.settings, "gemini_api_key", "")
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        llm_client.call_structured(
            model="gemini-2.5-flash",
            system_prompt="sys",
            user_prompt="user",
            tool_name="t",
            tool_description="d",
            input_schema=_DummySchema.model_json_schema(),
            response_model=_DummySchema,
        )


def test_invoke_gemini_success_parses_json_text(monkeypatch):
    from app.core import llm_client

    fake_response = SimpleNamespace(text='{"value": "hello"}', prompt_feedback=None)
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: fake_response)
    )
    monkeypatch.setattr(llm_client, "_get_gemini_client", lambda: fake_client)

    result = llm_client._invoke_gemini(
        model="gemini-2.5-flash",
        system_prompt="sys",
        user_prompt="user",
        input_schema=_DummySchema.model_json_schema(),
        max_tokens=4096,
    )
    assert result == {"value": "hello"}


def test_call_structured_end_to_end_with_gemini_provider(monkeypatch):
    """Full call_structured() -> _invoke_tool() -> _invoke_gemini() path
    with LLM_PROVIDER=gemini, confirming the provider dispatch and the
    Pydantic second-validation-layer both work for the Gemini branch, not
    just the Anthropic one."""
    from app.core import llm_client

    monkeypatch.setattr(llm_client.settings, "llm_provider", "gemini")
    monkeypatch.setattr(llm_client.settings, "gemini_api_key", "fake-key")

    fake_response = SimpleNamespace(text='{"value": "hello"}', prompt_feedback=None)
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: fake_response)
    )
    monkeypatch.setattr(llm_client, "_get_gemini_client", lambda: fake_client)

    result = llm_client.call_structured(
        model="gemini-2.5-flash",
        system_prompt="sys",
        user_prompt="user",
        tool_name="t",
        tool_description="d",
        input_schema=_DummySchema.model_json_schema(),
        response_model=_DummySchema,
    )
    assert result.value == "hello"


def test_invoke_gemini_normalizes_server_error_to_transient(monkeypatch):
    from google.genai import errors as genai_errors

    from app.core import llm_client

    server_error = genai_errors.ServerError(503, {"error": {"message": "overloaded"}})
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: (_ for _ in ()).throw(server_error))
    )
    monkeypatch.setattr(llm_client, "_get_gemini_client", lambda: fake_client)

    with pytest.raises(llm_client._TransientProviderError):
        llm_client._invoke_gemini(
            model="gemini-2.5-flash",
            system_prompt="sys",
            user_prompt="user",
            input_schema=_DummySchema.model_json_schema(),
            max_tokens=4096,
        )


def test_invoke_gemini_normalizes_rate_limit_to_transient(monkeypatch):
    from google.genai import errors as genai_errors

    from app.core import llm_client

    rate_limit_error = genai_errors.ClientError(429, {"error": {"message": "rate limited"}})
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: (_ for _ in ()).throw(rate_limit_error))
    )
    monkeypatch.setattr(llm_client, "_get_gemini_client", lambda: fake_client)

    with pytest.raises(llm_client._TransientProviderError):
        llm_client._invoke_gemini(
            model="gemini-2.5-flash",
            system_prompt="sys",
            user_prompt="user",
            input_schema=_DummySchema.model_json_schema(),
            max_tokens=4096,
        )


def test_invoke_gemini_normalizes_bad_request_to_non_retryable(monkeypatch):
    from google.genai import errors as genai_errors

    from app.core import llm_client

    bad_request_error = genai_errors.ClientError(400, {"error": {"message": "bad request"}})
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: (_ for _ in ()).throw(bad_request_error))
    )
    monkeypatch.setattr(llm_client, "_get_gemini_client", lambda: fake_client)

    with pytest.raises(llm_client._NonRetryableProviderError):
        llm_client._invoke_gemini(
            model="gemini-2.5-flash",
            system_prompt="sys",
            user_prompt="user",
            input_schema=_DummySchema.model_json_schema(),
            max_tokens=4096,
        )


def test_invoke_gemini_raises_non_retryable_on_blocked_response(monkeypatch):
    from app.core import llm_client

    fake_response = SimpleNamespace(text=None, prompt_feedback=SimpleNamespace(block_reason="SAFETY"))
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: fake_response)
    )
    monkeypatch.setattr(llm_client, "_get_gemini_client", lambda: fake_client)

    with pytest.raises(llm_client._NonRetryableProviderError, match="SAFETY"):
        llm_client._invoke_gemini(
            model="gemini-2.5-flash",
            system_prompt="sys",
            user_prompt="user",
            input_schema=_DummySchema.model_json_schema(),
            max_tokens=4096,
        )


def test_invoke_gemini_raises_non_retryable_on_invalid_json(monkeypatch):
    from app.core import llm_client

    fake_response = SimpleNamespace(text="not json {{{", prompt_feedback=None)
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **_: fake_response)
    )
    monkeypatch.setattr(llm_client, "_get_gemini_client", lambda: fake_client)

    with pytest.raises(llm_client._NonRetryableProviderError, match="valid JSON"):
        llm_client._invoke_gemini(
            model="gemini-2.5-flash",
            system_prompt="sys",
            user_prompt="user",
            input_schema=_DummySchema.model_json_schema(),
            max_tokens=4096,
        )
