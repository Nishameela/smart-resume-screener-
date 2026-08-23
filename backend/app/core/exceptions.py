"""
Application-specific exception hierarchy.

Every exception carries an HTTP status code and a machine-readable
`code` string so the global exception handler (see app/main.py) can
translate it into a consistent JSON error envelope:

    {"error": {"code": "...", "message": "..."}}

Never let a bare Exception escape a route handler -- catch it at the
service boundary and re-raise as one of these, or let the global
handler turn it into a generic 500 with no internal detail leaked.
"""


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ValidationAppError(AppError):
    """Malformed or disallowed input from the client (bad file, missing field)."""

    status_code = 400
    code = "validation_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ExtractionError(AppError):
    """Text could not be reliably extracted from the uploaded file."""

    status_code = 422
    code = "extraction_error"


class LLMError(AppError):
    """The LLM provider failed, timed out, or returned output we could not
    validate even after a corrective retry."""

    status_code = 502
    code = "llm_error"
