"""
Second ad-hoc smoke test (not part of the shipped repo): drives the
real frontend build through the full Setup -> Rankings -> Detail flow
using Playwright's network interception to stand in for the backend
responses (since this environment has no ANTHROPIC_API_KEY yet to
exercise a real LLM call). Response payloads are shaped exactly like
the real Pydantic schemas so this genuinely exercises the rendering
code paths -- score gauge, badges, requirement evidence matrix, skills
comparison -- not just "did the page load".
"""
import re
import sys
from playwright.sync_api import sync_playwright

FRONTEND_URL = "http://127.0.0.1:4173"
FIXTURE_PDF = "/home/claude/smart-resume-screener/backend/tests/fixtures/sample_resume.pdf"

JD_RESPONSE = {
    "id": 1,
    "job_title": "Backend Engineer",
    "created_at": "2026-08-23T12:00:00",
    "requirements": [
        {"id": 1, "requirement_text": "3+ years of Python backend development", "priority": "must_have", "category": "experience"},
        {"id": 2, "requirement_text": "Experience with FastAPI or Flask", "priority": "must_have", "category": "skill"},
        {"id": 3, "requirement_text": "Experience with PostgreSQL", "priority": "preferred", "category": "skill"},
    ],
}

RESUME_RESPONSE = {
    "id": 1,
    "filename": "sample_resume.pdf",
    "file_type": "pdf",
    "candidate_name": "Jordan Lee",
    "candidate_email": "jordan.lee@example.com",
    "processing_status": "completed",
    "error_message": None,
    "created_at": "2026-08-23T12:00:00",
    "skills": [
        {"raw_text": "Python", "canonical_name": "Python", "category": "language", "match_type": "exact"},
        {"raw_text": "FastAPI", "canonical_name": "FastAPI", "category": "framework", "match_type": "exact"},
        {"raw_text": "Postgres", "canonical_name": "PostgreSQL", "category": "database", "match_type": "normalized"},
    ],
    "experience_entries": [
        {
            "title": "Backend Engineer",
            "company": "Acme Corp",
            "start_date": "2021",
            "end_date": None,
            "is_current": True,
            "description": "Built REST APIs using Python and FastAPI, deployed on AWS.",
        }
    ],
    "education_entries": [
        {"degree": "B.S. Computer Science", "institution": "State University", "field_of_study": "Computer Science", "graduation_year": "2021"}
    ],
}

EVALUATION_RESPONSE = {
    "id": 1,
    "resume_id": 1,
    "jd_id": 1,
    "overall_score": 91.7,
    "deterministic_component": 100.0,
    "llm_component": 91.7,
    "confidence": 0.92,
    "ai_summary": "A strong candidate for further review, with direct, well-evidenced backend experience.",
    "strengths": ["Direct Python + FastAPI backend experience", "Clear ownership of production APIs"],
    "gaps": ["No explicit PostgreSQL experience demonstrated"],
    "interview_focus_areas": ["Depth of PostgreSQL/database design experience"],
    "llm_status": "success",
    "created_at": "2026-08-23T12:00:00",
    "requirement_matches": [
        {
            "requirement_text": "3+ years of Python backend development",
            "priority": "must_have",
            "category": "experience",
            "match_level": "strong",
            "evidence": ["Built REST APIs using Python and FastAPI, deployed on AWS."],
            "reasoning": "Resume shows ongoing Python backend role since 2021 with direct API-building evidence.",
            "confidence": 0.95,
        },
        {
            "requirement_text": "Experience with FastAPI or Flask",
            "priority": "must_have",
            "category": "skill",
            "match_level": "strong",
            "evidence": ["Built REST APIs using Python and FastAPI"],
            "reasoning": "FastAPI explicitly named and used in a real project.",
            "confidence": 0.97,
        },
        {
            "requirement_text": "Experience with PostgreSQL",
            "priority": "preferred",
            "category": "skill",
            "match_level": "partial",
            "evidence": [],
            "reasoning": "Candidate lists Postgres as a skill but no project explicitly demonstrates database work.",
            "confidence": 0.6,
        },
    ],
}

EVALUATION_LIST_RESPONSE = [
    {
        "id": 1,
        "resume_id": 1,
        "candidate_name": "Jordan Lee",
        "filename": "sample_resume.pdf",
        "overall_score": 91.7,
        "confidence": 0.92,
        "llm_status": "success",
        "top_strength": "Direct Python + FastAPI backend experience",
        "biggest_gap": "No explicit PostgreSQL experience demonstrated",
        "created_at": "2026-08-23T12:00:00",
    }
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        page.route(re.compile(r".*/api/job-descriptions$"), lambda route: route.fulfill(status=201, json=JD_RESPONSE))
        page.route(re.compile(r".*/api/resumes$"), lambda route: route.fulfill(status=201, json=RESUME_RESPONSE))
        page.route(re.compile(r".*/api/resumes/1$"), lambda route: route.fulfill(status=200, json=RESUME_RESPONSE))
        page.route(re.compile(r".*/api/evaluations$"), lambda route: route.fulfill(status=201, json=EVALUATION_RESPONSE))
        page.route(re.compile(r".*/api/evaluations\?jd_id=1$"), lambda route: route.fulfill(status=200, json=EVALUATION_LIST_RESPONSE))
        page.route(re.compile(r".*/api/evaluations/1$"), lambda route: route.fulfill(status=200, json=EVALUATION_RESPONSE))

        page.goto(FRONTEND_URL, wait_until="networkidle")
        page.fill("#jd-text", "We are hiring a Backend Engineer with 3+ years of Python backend development experience.")
        page.set_input_files('input[type="file"]', FIXTURE_PDF)
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Analyze Candidates").click()

        page.wait_for_selector("text=Candidate Rankings", timeout=10000)
        print("[OK] Navigated to Rankings screen after successful analysis")

        page.wait_for_selector("text=Jordan Lee", timeout=5000)
        page.wait_for_selector("text=Direct Python + FastAPI backend experience", timeout=5000)
        print("[OK] Ranking card shows candidate name and top strength")

        page.get_by_text("Jordan Lee").click()
        page.wait_for_selector("text=Requirement-by-Requirement Match", timeout=5000)
        print("[OK] Navigated to Candidate Detail screen")

        page.wait_for_selector("text=Built REST APIs using Python and FastAPI, deployed on AWS.", timeout=5000)
        print("[OK] Evidence quote rendered in requirement match card")

        page.wait_for_selector("text=PostgreSQL", timeout=5000)
        page.wait_for_selector("text=Normalized", timeout=5000)
        print("[OK] Skill normalization badge (Postgres -> PostgreSQL, Normalized) rendered")

        page.wait_for_selector("text=A strong candidate for further review", timeout=5000)
        print("[OK] AI executive summary rendered")

        real_errors = [e for e in errors if "favicon" not in e.lower()]
        if real_errors:
            print("[FAIL] Console errors:")
            for e in real_errors:
                print("   ", e)
            sys.exit(1)
        print("[OK] No console errors")

        browser.close()
        print("\nHAPPY-PATH SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
