"""
One-off dev utility (not part of the shipped app) that converts two of
the four demo candidate .txt resumes into real text-based PDFs, so the
demo dataset exercises both required input formats (see
demo_data/README.md). Run with: python scripts/make_demo_pdfs.py
"""
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"

TO_CONVERT = [
    "candidate_1_strong_match_alex_chen.txt",
    "candidate_3_keyword_trap_sam_rivera.txt",
]


def make_pdf(src: Path, dest: Path) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in src.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            pdf.multi_cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            pdf.ln(6)
    pdf.output(str(dest))


if __name__ == "__main__":
    for filename in TO_CONVERT:
        src_path = DEMO_DIR / filename
        dest_path = src_path.with_suffix(".pdf")
        make_pdf(src_path, dest_path)
        src_path.unlink()  # keep one file per candidate, not both formats
        print(f"Wrote {dest_path}")
