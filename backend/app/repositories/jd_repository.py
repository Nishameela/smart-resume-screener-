from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.job_description import JDRequirement, JobDescription
from app.schemas.job_description import JDExtractionResult


def get_by_content_hash(db: Session, content_hash: str) -> JobDescription | None:
    return db.scalar(select(JobDescription).where(JobDescription.content_hash == content_hash))


def get_by_id(db: Session, jd_id: int) -> JobDescription | None:
    return db.get(JobDescription, jd_id)


def create_job_description(
    db: Session,
    *,
    raw_text: str,
    content_hash: str,
    extraction: JDExtractionResult,
) -> JobDescription:
    jd = JobDescription(raw_text=raw_text, job_title=extraction.job_title, content_hash=content_hash)
    for r in extraction.requirements:
        jd.requirements.append(
            JDRequirement(
                requirement_text=r.requirement_text,
                priority=r.priority,
                category=r.category,
            )
        )
    db.add(jd)
    db.commit()
    db.refresh(jd)
    return jd


def create_job_description_or_get_existing(
    db: Session,
    *,
    raw_text: str,
    content_hash: str,
    extraction: JDExtractionResult,
) -> tuple[JobDescription, bool]:
    """Insert, but tolerate losing a race against a concurrent submission of
    byte-identical JD text: content_hash's DB-level unique constraint
    rejects the second insert, so we roll back and hand back the winner's
    row (created=False) instead of surfacing a 500 for what is really just
    duplicate work."""
    try:
        return create_job_description(
            db, raw_text=raw_text, content_hash=content_hash, extraction=extraction
        ), True
    except IntegrityError:
        db.rollback()
        existing = get_by_content_hash(db, content_hash)
        if existing is None:
            raise  # not actually a duplicate-hash race; something else went wrong
        return existing, False
