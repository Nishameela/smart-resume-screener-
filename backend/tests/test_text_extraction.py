import pytest

from app.core.exceptions import ExtractionError
from app.services.file_validation import validate_upload
from app.services.text_extraction import extract_text
from tests.conftest import fixture_path


def _load(name: str):
    return fixture_path(name).read_bytes()


def test_extracts_text_from_real_pdf():
    v = validate_upload("sample_resume.pdf", _load("sample_resume.pdf"))
    text = extract_text(v)
    assert "Jordan Lee" in text
    assert "FastAPI" in text


def test_extracts_text_from_txt():
    v = validate_upload("sample_resume.txt", _load("sample_resume.txt"))
    text = extract_text(v)
    assert "Jordan Lee" in text


def test_corrupted_pdf_raises_extraction_error():
    v = validate_upload("corrupted.pdf", _load("corrupted.pdf"))
    with pytest.raises(ExtractionError, match="corrupted or unreadable"):
        extract_text(v)


def test_scanned_pdf_with_no_text_layer_raises_extraction_error():
    v = validate_upload("scanned_no_text.pdf", _load("scanned_no_text.pdf"))
    with pytest.raises(ExtractionError, match="scanned/image-based"):
        extract_text(v)


def test_whitespace_is_normalized():
    messy = (
        b"Summary line one about the candidate.\r\n\r\n\r\n\r\n"
        b"Second   section   with   irregular    spacing and enough text to pass the minimum length threshold."
    )
    v = validate_upload("messy.txt", messy)
    text = extract_text(v)
    assert "\n\n\n" not in text
    assert "   " not in text
