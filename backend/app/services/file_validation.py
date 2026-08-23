"""
Stage 1 of the resume pipeline: file validation.

Deliberately separated from extraction (stage 2) so each stage is
independently testable and failures are attributable to a specific
cause rather than a generic "something went wrong".
"""
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import ValidationAppError

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".txt": "txt"}


@dataclass(frozen=True)
class ValidatedFile:
    filename: str
    file_type: str  # "pdf" | "txt"
    content: bytes


def validate_upload(filename: str | None, content: bytes) -> ValidatedFile:
    if not filename:
        raise ValidationAppError("No filename provided.")

    suffix = _extension(filename)
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationAppError(
            f"Unsupported file type '{suffix or '(none)'}'. "
            f"Only PDF (.pdf) and plain text (.txt) resumes are accepted."
        )

    if not content:
        raise ValidationAppError(f"'{filename}' is empty.")

    if len(content) > settings.max_upload_size_bytes:
        raise ValidationAppError(
            f"'{filename}' exceeds the {settings.max_upload_size_mb}MB upload limit."
        )

    return ValidatedFile(filename=filename, file_type=ALLOWED_EXTENSIONS[suffix], content=content)


def _extension(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""
