from unittest.mock import patch

from app.schemas.job_description import JDExtractionResult
from app.schemas.resume_extraction import ResumeExtractionResult
from tests.conftest import fixture_path

SAMPLE_JD = (
    "We are hiring a Backend Engineer. Requirements: Python backend development "
    "experience is required. AWS experience is a plus."
)


def _fake_jd_extraction():
    return JDExtractionResult(
        job_title="Backend Engineer",
        requirements=[
            {"requirement_text": "Python backend development experience", "priority": "must_have", "category": "skill"},
            {"requirement_text": "AWS experience", "priority": "preferred", "category": "skill"},
        ],
    )


def _fake_resume_extraction():
    return ResumeExtractionResult(
        candidate_name="Jordan Lee",
        candidate_email="jordan.lee@example.com",
        skills=[{"name": "Python", "category": "language"}, {"name": "FastAPI", "category": "framework"}],
        experience=[
            {
                "title": "Backend Engineer",
                "company": "Acme Corp",
                "start_date": "2021",
                "end_date": "Present",
                "is_current": True,
                "description": "Built REST APIs using Python and FastAPI.",
            }
        ],
        education=[],
    )


def _fake_grounded_evaluation_result():
    return {
        "requirement_matches": [
            {
                "requirement_index": 1,
                "match_level": "strong",
                "evidence": ["Built REST APIs using Python and FastAPI"],
                "reasoning": "Direct evidence of Python backend development.",
                "confidence": 0.95,
            },
            {
                "requirement_index": 2,
                "match_level": "not_demonstrated",
                "evidence": [],
                "reasoning": "No AWS mention found in the resume.",
                "confidence": 0.9,
            },
        ],
        "summary": {
            "strengths": ["Direct, well-evidenced Python backend experience"],
            "gaps": ["No AWS or cloud experience demonstrated"],
            "executive_summary": "A strong candidate for further review.",
            "interview_focus_areas": ["Cloud/AWS exposure"],
        },
    }


def _setup_resume_and_jd(client):
    with patch("app.api.job_descriptions.parse_job_description", return_value=_fake_jd_extraction()):
        jd = client.post("/api/job-descriptions", json={"raw_text": SAMPLE_JD}).json()

    with patch("app.services.resume_parser.parse_resume", return_value=_fake_resume_extraction()):
        data = fixture_path("sample_resume.pdf").read_bytes()
        resume = client.post(
            "/api/resumes", files={"file": ("sample_resume.pdf", data, "application/pdf")}
        ).json()

    return resume, jd


def test_create_evaluation_end_to_end(client):
    resume, jd = _setup_resume_and_jd(client)

    from app.schemas.evaluation_llm import EvaluationLLMResult

    with patch(
        "app.services.llm_evaluator.call_structured",
        return_value=EvaluationLLMResult.model_validate(_fake_grounded_evaluation_result()),
    ):
        resp = client.post("/api/evaluations", json={"resume_id": resume["id"], "jd_id": jd["id"]})

    assert resp.status_code == 201
    body = resp.json()
    assert body["llm_status"] == "success"
    assert 0 <= body["overall_score"] <= 100
    assert len(body["requirement_matches"]) == 2
    strong_matches = [m for m in body["requirement_matches"] if m["match_level"] == "strong"]
    assert len(strong_matches) == 1
    assert "FastAPI" in strong_matches[0]["evidence"][0]


def test_list_evaluations_ranked_for_jd(client):
    resume, jd = _setup_resume_and_jd(client)

    from app.schemas.evaluation_llm import EvaluationLLMResult

    with patch(
        "app.services.llm_evaluator.call_structured",
        return_value=EvaluationLLMResult.model_validate(_fake_grounded_evaluation_result()),
    ):
        client.post("/api/evaluations", json={"resume_id": resume["id"], "jd_id": jd["id"]})

    resp = client.get(f"/api/evaluations?jd_id={jd['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["candidate_name"] == "Jordan Lee"
    assert body[0]["top_strength"] is not None
    assert body[0]["biggest_gap"] is not None


def test_evaluation_for_unstructured_resume_returns_422(client):
    with patch("app.api.job_descriptions.parse_job_description", return_value=_fake_jd_extraction()):
        jd = client.post("/api/job-descriptions", json={"raw_text": SAMPLE_JD}).json()

    # Upload without mocking parse_resume -> structuring fails (no API key) -> status FAILED
    data = fixture_path("sample_resume.pdf").read_bytes()
    resume = client.post(
        "/api/resumes", files={"file": ("sample_resume.pdf", data, "application/pdf")}
    ).json()
    assert resume["processing_status"] == "failed"

    resp = client.post("/api/evaluations", json={"resume_id": resume["id"], "jd_id": jd["id"]})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_evaluation_with_nonexistent_ids_returns_404(client):
    resp = client.post("/api/evaluations", json={"resume_id": 999, "jd_id": 999})
    assert resp.status_code == 404
