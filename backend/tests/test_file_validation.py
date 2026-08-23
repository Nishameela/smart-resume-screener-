import pytest

from app.core.exceptions import ValidationAppError
from app.services.file_validation import validate_upload


def test_accepts_pdf():
    v = validate_upload("resume.pdf", b"%PDF-1.4 fake but non-empty")
    assert v.file_type == "pdf"


def test_accepts_txt():
    v = validate_upload("resume.txt", b"hello")
    assert v.file_type == "txt"


def test_rejects_missing_filename():
    with pytest.raises(ValidationAppError):
        validate_upload(None, b"hello")


def test_rejects_unsupported_extension():
    with pytest.raises(ValidationAppError, match="Unsupported file type"):
        validate_upload("resume.docx", b"hello")


def test_rejects_empty_content():
    with pytest.raises(ValidationAppError, match="empty"):
        validate_upload("resume.txt", b"")


def test_rejects_oversized_file():
    from app.core.config import settings

    too_big = b"x" * (settings.max_upload_size_bytes + 1)
    with pytest.raises(ValidationAppError, match="exceeds"):
        validate_upload("resume.txt", too_big)


def test_extension_matching_is_case_insensitive():
    v = validate_upload("Resume.PDF", b"%PDF-1.4 fake but non-empty")
    assert v.file_type == "pdf"
