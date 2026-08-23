from unittest.mock import patch

from app.schemas.job_description import JDExtractionResult

SAMPLE_JD = (
    "We are hiring a Backend Engineer. Requirements: 3+ years of Python backend "
    "development, experience with FastAPI or Flask, and a Bachelor's degree in "
    "Computer Science or related field. Nice to have: experience with PostgreSQL."
)


def _fake_extraction():
    return JDExtractionResult(
        job_title="Backend Engineer",
        requirements=[
            {
                "requirement_text": "3+ years of Python backend development",
                "priority": "must_have",
                "category": "experience",
            },
            {
                "requirement_text": "Experience with FastAPI or Flask",
                "priority": "must_have",
                "category": "skill",
            },
            {
                "requirement_text": "Bachelor's degree in Computer Science or related field",
                "priority": "must_have",
                "category": "education",
            },
            {
                "requirement_text": "Experience with PostgreSQL",
                "priority": "preferred",
                "category": "skill",
            },
        ],
    )


def test_create_job_description_returns_structured_requirements(client):
    with patch("app.api.job_descriptions.parse_job_description", return_value=_fake_extraction()):
        resp = client.post("/api/job-descriptions", json={"raw_text": SAMPLE_JD})

    assert resp.status_code == 201
    body = resp.json()
    assert body["job_title"] == "Backend Engineer"
    assert len(body["requirements"]) == 4
    must_haves = [r for r in body["requirements"] if r["priority"] == "must_have"]
    assert len(must_haves) == 3


def test_duplicate_jd_does_not_call_llm_again(client):
    with patch(
        "app.api.job_descriptions.parse_job_description", return_value=_fake_extraction()
    ) as mock_parse:
        first = client.post("/api/job-descriptions", json={"raw_text": SAMPLE_JD}).json()
        second = client.post("/api/job-descriptions", json={"raw_text": SAMPLE_JD}).json()

    assert first["id"] == second["id"]
    mock_parse.assert_called_once()


def test_jd_too_short_returns_422(client):
    resp = client.post("/api/job-descriptions", json={"raw_text": "too short"})
    assert resp.status_code == 422  # FastAPI/Pydantic request validation


def test_get_nonexistent_jd_returns_404(client):
    resp = client.get("/api/job-descriptions/999")
    assert resp.status_code == 404
