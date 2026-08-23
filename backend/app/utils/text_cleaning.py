import re


def normalize_whitespace(text: str) -> str:
    """Collapse repeated blank lines/spaces produced by PDF extraction
    without destroying paragraph structure -- keeps LLM prompts compact
    (lower token cost) and makes content hashing stable regardless of
    incidental whitespace differences between two uploads of "the same"
    resume."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
