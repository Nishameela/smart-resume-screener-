from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import jd_repository
from app.schemas.job_description import JobDescriptionCreate, JobDescriptionOut
from app.services.jd_parser import parse_job_description
from app.utils.hashing import sha256_of_text
from app.utils.text_cleaning import normalize_whitespace

router = APIRouter(prefix="/job-descriptions", tags=["job-descriptions"])


@router.post("", response_model=JobDescriptionOut, status_code=201)
def create_job_description(
    payload: JobDescriptionCreate, response: Response, db: Session = Depends(get_db)
) -> JobDescriptionOut:
    text = normalize_whitespace(payload.raw_text)
    content_hash = sha256_of_text(text)

    existing = jd_repository.get_by_content_hash(db, content_hash)
    if existing is not None:
        # Same content already ingested -- this is a lookup, not a creation.
        response.status_code = 200
        return JobDescriptionOut.model_validate(existing)

    extraction = parse_job_description(text)
    jd, _created = jd_repository.create_job_description_or_get_existing(
        db, raw_text=text, content_hash=content_hash, extraction=extraction
    )
    return JobDescriptionOut.model_validate(jd)


@router.get("/{jd_id}", response_model=JobDescriptionOut)
def get_job_description(jd_id: int, db: Session = Depends(get_db)) -> JobDescriptionOut:
    jd = jd_repository.get_by_id(db, jd_id)
    if jd is None:
        raise NotFoundError(f"Job description {jd_id} not found.")
    return JobDescriptionOut.model_validate(jd)
