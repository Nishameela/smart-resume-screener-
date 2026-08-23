"""
Ad-hoc smoke test (not part of the shipped repo) that drives the real
running frontend + backend with a headless browser to verify the UI
actually renders and talks to the API -- not just that `tsc`/`vite
build` succeed. Requires both servers already running:
  backend:  uvicorn app.main:app --port 8000
  frontend: vite preview --port 4173 (or `npm run dev`)
"""
import sys
from playwright.sync_api import sync_playwright

FRONTEND_URL = "http://127.0.0.1:4173"
FIXTURE_PDF = "/home/claude/smart-resume-screener/backend/tests/fixtures/sample_resume.pdf"

console_errors = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        page.goto(FRONTEND_URL, wait_until="networkidle")
        assert page.title() == "Smart Resume Screener", f"unexpected title: {page.title()}"

        heading = page.locator("h1", has_text="Smart Resume Screener")
        assert heading.is_visible(), "main heading not visible"
        print("[OK] Setup screen renders with correct heading")

        jd_text = (
            "We are hiring a Backend Engineer. Requirements: 3+ years of Python backend "
            "development, experience with FastAPI or Flask, and a Bachelor's degree in "
            "Computer Science. Nice to have: experience with PostgreSQL."
        )
        page.fill("#jd-text", jd_text)
        print("[OK] Filled job description textarea")

        page.set_input_files('input[type="file"]', FIXTURE_PDF)
        page.wait_for_selector("text=sample_resume.pdf", timeout=5000)
        print("[OK] File added to upload list")

        analyze_button = page.get_by_role("button", name="Analyze Candidates")
        assert analyze_button.is_enabled(), "Analyze button should be enabled with valid JD + 1 file"
        analyze_button.click()
        print("[OK] Clicked Analyze Candidates")

        # No ANTHROPIC_API_KEY is configured in this environment, so JD
        # parsing itself will fail -- verify that surfaces as a clean
        # error banner rather than a blank page or unhandled exception.
        page.wait_for_selector("text=ANTHROPIC_API_KEY", timeout=10000)
        print("[OK] Graceful error banner shown when LLM is unavailable (no crash, no blank page)")

        # Chrome auto-logs a console error for any non-2xx fetch response
        # (e.g. "Failed to load resource: ... 502") -- that's expected
        # here since we deliberately exercised the no-API-key failure
        # path, not a bug. Only flag errors that aren't that expected
        # network-status log line.
        real_errors = [
            e
            for e in console_errors
            if "favicon" not in e.lower() and "Failed to load resource" not in e
        ]
        if real_errors:
            print("[FAIL] Console errors detected:")
            for e in real_errors:
                print("   ", e)
            sys.exit(1)
        print("[OK] No unexpected console errors")

        browser.close()
        print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
