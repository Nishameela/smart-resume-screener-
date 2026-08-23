from unittest.mock import patch

from app.schemas.resume_extraction import ResumeExtractionResult
from tests.conftest import fixture_path


def _upload(client, filename, content_type="application/octet-stream", fixture_name=None):
    data = fixture_path(fixture_name or filename).read_bytes()
    return client.post("/api/resumes", files={"file": (filename, data, content_type)})


def _fake_extraction():
    return ResumeExtractionResult(
        candidate_name="Jordan Lee",
        candidate_email="jordan.lee@example.com",
        skills=[
            {"name": "Python", "category": "language"},
            {"name": "FastAPI", "category": "framework"},
        ],
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
        education=[
            {
                "degree": "B.S.",
                "institution": "State University",
                "field_of_study": "Computer Science",
                "graduation_year": "2021",
            }
        ],
    )


def test_upload_valid_pdf_without_llm_key_still_returns_201_with_failed_structuring(client):
    # No ANTHROPIC_API_KEY is configured in the test environment -- the
    # upload should still succeed (text extraction worked) but structured
    # extraction should fail gracefully rather than crash the request.
    resp = _upload(client, "sample_resume.pdf", "application/pdf")
    assert resp.status_code == 201
    body = resp.json()
    assert body["processing_status"] == "failed"
    assert "ANTHROPIC_API_KEY" in body["error_message"]


def test_upload_with_successful_structured_extraction(client):
    with patch(
        "app.services.resume_parser.parse_resume", return_value=_fake_extraction()
    ):
        resp = _upload(client, "sample_resume.pdf", "application/pdf")

    assert resp.status_code == 201
    body = resp.json()
    assert body["processing_status"] == "completed"
    assert body["candidate_name"] == "Jordan Lee"
    assert body["candidate_email"] == "jordan.lee@example.com"
    assert {s["raw_text"] for s in body["skills"]} == {"Python", "FastAPI"}
    assert body["experience_entries"][0]["company"] == "Acme Corp"
    assert body["education_entries"][0]["institution"] == "State University"


def test_duplicate_upload_returns_same_resume(client):
    with patch("app.services.resume_parser.parse_resume", return_value=_fake_extraction()):
        first_resp = _upload(client, "sample_resume.pdf", "application/pdf")
        second_resp = _upload(client, "sample_resume.pdf", "application/pdf")
    first, second = first_resp.json(), second_resp.json()
    assert first["id"] == second["id"]
    # First upload creates (201); the duplicate is a lookup, not a creation (200).
    assert first_resp.status_code == 201
    assert second_resp.status_code == 200

    listing = client.get("/api/resumes").json()
    assert len(listing) == 1


def test_upload_empty_file_returns_400(client):
    resp = _upload(client, "empty.txt", "text/plain")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_upload_corrupted_pdf_returns_422(client):
    resp = _upload(client, "corrupted.pdf", "application/pdf")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "extraction_error"


def test_upload_unsupported_type_returns_400(client):
    resp = client.post(
        "/api/resumes", files={"file": ("resume.docx", b"some content", "application/msword")}
    )
    assert resp.status_code == 400


def test_get_nonexistent_resume_returns_404(client):
    resp = client.get("/api/resumes/999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
