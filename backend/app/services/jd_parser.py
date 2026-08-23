from app.core.config import settings
from app.core.llm_client import call_structured
from app.prompts.jd_analysis import SYSTEM_PROMPT, TOOL_DESCRIPTION, TOOL_NAME, build_user_prompt
from app.schemas.job_description import JDExtractionResult


def parse_job_description(jd_text: str) -> JDExtractionResult:
    """LLM Prompt B: turn raw JD text into structured, prioritized
    requirements. Raises LLMError (via call_structured) if the model
    cannot produce valid output within the configured retry budget --
    callers decide how to surface that to the client."""
    return call_structured(
        model=settings.model_for_extraction,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(jd_text),
        tool_name=TOOL_NAME,
        tool_description=TOOL_DESCRIPTION,
        input_schema=JDExtractionResult.model_json_schema(),
        response_model=JDExtractionResult,
    )
