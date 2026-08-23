"""
Runs the full pipeline against demo_data/ using real LLM calls, going
through the exact same service functions the API routes use (not a
separate/parallel implementation) -- upload/extract -> JD parse -> resume
parse -> evaluate -- against the app's real database, so the results are
also browsable afterward by starting the app normally (uvicorn + npm run
dev) and opening the frontend.

Usage (from backend/, with venv activated and .env configured):
    python ../scripts/run_demo.py

Prints a ranked score table and the requirement-by-requirement breakdown
for the two candidates the "keyword trap" narrative depends on, then
reports whether the keyword-trap candidate actually scored lower than the
transferable-match candidate -- the core design claim this dataset exists
to validate. Never fabricates or adjusts anything: whatever the real LLM
returns is what gets printed.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
DEMO_DATA_DIR = Path(__file__).resolve().parent.parent / "demo_data"
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models  # noqa: E402,F401
from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.core.exceptions import LLMError  # noqa: E402
from app.repositories import evaluation_repository, jd_repository, resume_repository  # noqa: E402
from app.services import evaluation_service, jd_parser, resume_parser  # noqa: E402
from app.services.file_validation import validate_upload  # noqa: E402
from app.services.text_extraction import extract_text  # noqa: E402
from app.utils.hashing import sha256_of_text  # noqa: E402
from app.utils.text_cleaning import normalize_whitespace  # noqa: E402

CANDIDATES = [
    ("candidate_1_strong_match_alex_chen.pdf", "Strong match (Alex Chen)"),
    ("candidate_2_partial_match_priya_sharma.txt", "Partial match (Priya Sharma)"),
    ("candidate_3_keyword_trap_sam_rivera.pdf", "Keyword trap (Sam Rivera)"),
    ("candidate_4_transferable_match_jordan_kim.txt", "Transferable match (Jordan Kim)"),
]


def _ingest_resume(db, filename: str):
    path = DEMO_DATA_DIR / filename
    content = path.read_bytes()
    validated = validate_upload(filename, content)
    text = extract_text(validated)
    content_hash = sha256_of_text(text)

    existing = resume_repository.get_by_content_hash(db, content_hash)
    if existing is not None:
        return existing

    resume, created = resume_repository.create_resume_or_get_existing(
        db, filename=validated.filename, file_type=validated.file_type,
        raw_text=text, content_hash=content_hash,
    )
    if created:
        resume = resume_parser.run_structured_extraction(db, resume)
    return resume


def _ingest_jd(db):
    text = normalize_whitespace((DEMO_DATA_DIR / "job_description.txt").read_text())
    content_hash = sha256_of_text(text)
    existing = jd_repository.get_by_content_hash(db, content_hash)
    if existing is not None:
        return existing
    extraction = jd_parser.parse_job_description(text)
    jd, _created = jd_repository.create_job_description_or_get_existing(
        db, raw_text=text, content_hash=content_hash, extraction=extraction
    )
    return jd


def main() -> int:
    print(f"LLM_PROVIDER = {settings.llm_provider}, model = {settings.resolved_default_model}")
    print(f"database     = {settings.database_url}\n")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    print("Ingesting job description...")
    jd = _ingest_jd(db)
    print(f"  JD id={jd.id}, title={jd.job_title!r}, {len(jd.requirements)} requirements\n")

    results = []
    for filename, label in CANDIDATES:
        print(f"Ingesting + evaluating: {label} ({filename})")
        resume = _ingest_resume(db, filename)
        if resume.processing_status.value != "completed":
            print(f"  WARNING: structured extraction did not complete "
                  f"(status={resume.processing_status.value}): {resume.error_message}")
        try:
            evaluation = evaluation_service.get_or_create_evaluation(db, resume.id, jd.id)
        except LLMError as exc:
            print(f"  FAILED: {exc}")
            return 1
        results.append((label, resume, evaluation))
        print(f"  overall_score={evaluation.overall_score}  llm_status={evaluation.llm_status.value}\n")

    print("=" * 70)
    print("RANKED RESULTS")
    print("=" * 70)
    ranked = sorted(results, key=lambda r: r[2].overall_score, reverse=True)
    for rank, (label, resume, evaluation) in enumerate(ranked, start=1):
        print(
            f"{rank}. {label:38s} score={evaluation.overall_score:6.1f}  "
            f"deterministic={evaluation.deterministic_component}  "
            f"llm={evaluation.llm_component}  confidence={evaluation.confidence}"
        )

    print("\n" + "=" * 70)
    print("REQUIREMENT-BY-REQUIREMENT: keyword trap vs transferable match")
    print("=" * 70)
    for label, resume, evaluation in results:
        if "keyword trap" not in label.lower() and "transferable" not in label.lower():
            continue
        print(f"\n--- {label} (overall {evaluation.overall_score}) ---")
        full = evaluation_repository.get_by_id(db, evaluation.id)
        for m in full.requirement_matches:
            print(f"  [{m.match_level.value:16s}] {m.requirement.requirement_text}")
            print(f"      reasoning: {m.reasoning}")
            if m.evidence:
                print(f"      evidence:  {m.evidence}")

    trap = next(e for label, r, e in results if "keyword trap" in label.lower())
    transferable = next(e for label, r, e in results if "transferable" in label.lower())
    print("\n" + "=" * 70)
    if trap.overall_score < transferable.overall_score:
        print(
            f"PASS: keyword-trap candidate ({trap.overall_score}) scored lower than "
            f"the transferable-match candidate ({transferable.overall_score}), as designed."
        )
        return 0
    else:
        print(
            f"WARNING: keyword-trap candidate ({trap.overall_score}) did NOT score lower "
            f"than the transferable-match candidate ({transferable.overall_score}). "
            f"Review the reasoning above -- this may warrant a scoring_config.py tune."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
