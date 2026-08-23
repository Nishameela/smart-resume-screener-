from unittest.mock import patch

from app.schemas.job_description import JDExtractionResult


def test_parse_job_description_returns_validated_result(monkeypatch):
    from app.services import jd_parser

    fake_result = JDExtractionResult(
        job_title="Backend Engineer",
        requirements=[
            {"requirement_text": "3+ years Python", "priority": "must_have", "category": "experience"},
            {"requirement_text": "FastAPI", "priority": "preferred", "category": "skill"},
        ],
    )

    with patch.object(jd_parser, "call_structured", return_value=fake_result) as mock_call:
        result = jd_parser.parse_job_description("some jd text")

    assert result.job_title == "Backend Engineer"
    assert len(result.requirements) == 2
    assert result.requirements[0].priority == "must_have"
    mock_call.assert_called_once()
