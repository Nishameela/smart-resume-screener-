from fastapi import APIRouter, Depends, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import resume_repository
from app.schemas.resume import ResumeOut, ResumeSummaryOut
from app.services.file_validation import validate_upload
from app.services.resume_parser import run_structured_extraction
from app.services.text_extraction import extract_text
from app.utils.hashing import sha256_of_text

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", response_model=ResumeOut, status_code=201)
async def upload_resume(file: UploadFile, response: Response, db: Session = Depends(get_db)) -> ResumeOut:
    content = await file.read()
    validated = validate_upload(file.filename, content)
    text = extract_text(validated)
    content_hash = sha256_of_text(text)

    existing = resume_repository.get_by_content_hash(db, content_hash)
    if existing is not None:
        # Same content already ingested -- this is a lookup, not a creation.
        response.status_code = 200
        return ResumeOut.model_validate(existing)

    resume, created = resume_repository.create_resume_or_get_existing(
        db,
        filename=validated.filename,
        file_type=validated.file_type,
        raw_text=text,
        content_hash=content_hash,
    )
    if not created:
        # Lost a race to a concurrent upload of the same content -- the
        # winner's row already has (or is getting) structured extraction;
        # don't run it a second time.
        response.status_code = 200
        return ResumeOut.model_validate(resume)
    # Text extraction succeeded. Structured (LLM) extraction runs next and
    # never raises -- a failure here still leaves the resume record usable
    # (raw text + a clear error_message) rather than failing the upload.
    resume = run_structured_extraction(db, resume)
    return ResumeOut.model_validate(resume)


@router.get("", response_model=list[ResumeSummaryOut])
def list_resumes(db: Session = Depends(get_db)) -> list[ResumeSummaryOut]:
    return [ResumeSummaryOut.model_validate(r) for r in resume_repository.list_all(db)]


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: int, db: Session = Depends(get_db)) -> ResumeOut:
    resume = resume_repository.get_by_id(db, resume_id)
    if resume is None:
        raise NotFoundError(f"Resume {resume_id} not found.")
    return ResumeOut.model_validate(resume)
