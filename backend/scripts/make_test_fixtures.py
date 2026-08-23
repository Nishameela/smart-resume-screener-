"""
One-off dev utility (not part of the shipped app) to generate binary
test fixtures that can't reasonably be hand-written: a real text-based
PDF, an image-only PDF with no extractable text layer, and a corrupted
"PDF" file. Run with: python scripts/make_test_fixtures.py
"""
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

RESUME_TEXT = """Jordan Lee
jordan.lee@example.com

EXPERIENCE
Backend Engineer, Acme Corp (2021 - Present)
Built REST APIs using Python and FastAPI, deployed on AWS. Designed
PostgreSQL schemas for a multi-tenant billing system serving 50k users.

Software Engineer Intern, Beta Labs (2020 - 2021)
Worked on data pipelines in Python, wrote unit tests with pytest.

EDUCATION
B.S. Computer Science, State University, 2021

SKILLS
Python, FastAPI, PostgreSQL, Docker, Git, REST APIs
"""


def make_text_pdf(path: Path, text: str) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in text.split("\n"):
        if line.strip():
            pdf.multi_cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.ln(6)
    pdf.output(str(path))


def make_blank_image_pdf(path: Path) -> None:
    """A PDF with a drawn rectangle but no text layer at all -- simulates
    a scanned resume that pypdf cannot extract text from."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(200, 200, 200)
    pdf.rect(10, 10, 100, 50, style="F")
    pdf.output(str(path))


def make_corrupted_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4 this is not a valid pdf stream at all \x00\x01\x02")


if __name__ == "__main__":
    make_text_pdf(FIXTURES / "sample_resume.pdf", RESUME_TEXT)
    (FIXTURES / "sample_resume.txt").write_text(RESUME_TEXT, encoding="utf-8")
    (FIXTURES / "empty.txt").write_bytes(b"")
    make_corrupted_pdf(FIXTURES / "corrupted.pdf")
    make_blank_image_pdf(FIXTURES / "scanned_no_text.pdf")
    print(f"Fixtures written to {FIXTURES}")
