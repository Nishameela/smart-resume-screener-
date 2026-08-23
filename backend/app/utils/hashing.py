import hashlib


def sha256_of_text(text: str) -> str:
    """Content hash used for dedup (resumes, job descriptions) and as the
    cache key for LLM calls, so re-uploading identical content never
    re-triggers extraction or re-bills the LLM, and scores stay stable
    across reruns of the same input."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
