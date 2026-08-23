"""
Stage 2 of the resume pipeline: text extraction.

Handles PDF and plain-text input. Never pretends extraction succeeded
when it did not -- a PDF that yields too little text (a common symptom
of a scanned/image-only PDF that pypdf cannot OCR) raises a clear,
specific error rather than silently proceeding with near-empty content.
"""
import io

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.exceptions import ExtractionError
from app.services.file_validation import ValidatedFile
from app.utils.text_cleaning import normalize_whitespace

# Below this many characters, we treat extraction as having effectively
# failed (e.g. a scanned/image-based PDF with no embedded text layer)
# rather than proceeding with a near-empty resume profile.
MIN_EXTRACTED_CHARS = 50


def extract_text(file: ValidatedFile) -> str:
    if file.file_type == "pdf":
        raw = _extract_pdf_text(file.content)
    else:
        raw = _extract_plain_text(file.content)

    cleaned = normalize_whitespace(raw)

    if len(cleaned) < MIN_EXTRACTED_CHARS:
        raise ExtractionError(
            f"Could not extract enough readable text from '{file.filename}' "
            f"(got {len(cleaned)} characters). This usually means the PDF is "
            f"scanned/image-based rather than text-based, which this system "
            f"does not OCR. Please upload a text-based PDF or a .txt file."
        )

    return cleaned


def _extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
    except PdfReadError as exc:
        raise ExtractionError(f"The PDF file appears to be corrupted or unreadable: {exc}") from exc

    if reader.is_encrypted:
        raise ExtractionError("The PDF is password-protected and cannot be read.")

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception:  # pypdf can raise assorted low-level errors on malformed pages
            continue

    return "\n".join(pages_text)


def _extract_plain_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        # latin-1 maps every byte 0-255 to a character, so this decode can
        # never itself raise UnicodeDecodeError -- it's a deliberate
        # last-resort fallback for non-UTF-8 text files, not a validation
        # step. (A wrapping try/except here would be genuinely unreachable
        # dead code.)
        return content.decode("latin-1")
