"""
Persistence layer for Resume and its child entities. Business logic
(validation, extraction, scoring) never touches SQLAlchemy directly --
it goes through here, keeping services testable without a database.
"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.resume import EducationEntry, ExperienceEntry, Resume, ResumeSkill


def get_by_content_hash(db: Session, content_hash: str) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.content_hash == content_hash))


def get_by_id(db: Session, resume_id: int) -> Resume | None:
    return db.get(Resume, resume_id)


def list_all(db: Session) -> list[Resume]:
    return list(db.scalars(select(Resume).order_by(Resume.created_at.desc())))


def create_resume(
    db: Session,
    *,
    filename: str,
    file_type: str,
    raw_text: str,
    content_hash: str,
) -> Resume:
    resume = Resume(
        filename=filename,
        file_type=file_type,
        raw_text=raw_text,
        content_hash=content_hash,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def create_resume_or_get_existing(
    db: Session,
    *,
    filename: str,
    file_type: str,
    raw_text: str,
    content_hash: str,
) -> tuple[Resume, bool]:
    """Insert, but tolerate losing a race against a concurrent upload of
    byte-identical content: content_hash's DB-level unique constraint
    rejects the second insert, so we roll back and hand back the winner's
    row (created=False) instead of surfacing a 500 for what is really just
    duplicate work. Callers should skip re-running structured extraction
    when created is False, since the winner's row already has it (or has
    it in flight)."""
    try:
        return create_resume(
            db, filename=filename, file_type=file_type, raw_text=raw_text, content_hash=content_hash
        ), True
    except IntegrityError:
        db.rollback()
        existing = get_by_content_hash(db, content_hash)
        if existing is None:
            raise  # not actually a duplicate-hash race; something else went wrong
        return existing, False


def replace_structured_data(
    db: Session,
    resume: Resume,
    *,
    candidate_name: str | None,
    candidate_email: str | None,
    skills: list[dict],
    experience: list[dict],
    education: list[dict],
) -> Resume:
    """Idempotently (re)populate the structured child rows for a resume.
    Used by the LLM extraction stage (M5); safe to call again if a
    resume is reprocessed."""
    resume.candidate_name = candidate_name
    resume.candidate_email = candidate_email

    resume.skills.clear()
    resume.experience_entries.clear()
    resume.education_entries.clear()

    for s in skills:
        resume.skills.append(
            ResumeSkill(
                raw_text=s["raw_text"],
                canonical_name=s["canonical_name"],
                category=s.get("category"),
                match_type=s["match_type"],
            )
        )
    for e in experience:
        resume.experience_entries.append(ExperienceEntry(**e))
    for ed in education:
        resume.education_entries.append(EducationEntry(**ed))

    db.commit()
    db.refresh(resume)
    return resume


def set_status(db: Session, resume: Resume, status, error_message: str | None = None) -> Resume:
    resume.processing_status = status
    resume.error_message = error_message
    db.commit()
    db.refresh(resume)
    return resume
