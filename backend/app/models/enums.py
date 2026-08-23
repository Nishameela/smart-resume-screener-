"""
Shared enums used across the ORM models and (via the schemas layer) the
API contract. Centralizing these avoids magic strings scattered through
services, prompts, and the database layer.
"""
import enum


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SkillMatchType(str, enum.Enum):
    """How a raw resume skill string relates to its canonical name.

    EXACT: the raw text equals the canonical name (case-insensitive).
    NORMALIZED: the raw text is a known alias resolving to a different
        canonical name (e.g. "ReactJS" -> "React").
    UNMATCHED: no canonical mapping exists; the raw text is kept as-is.
    """

    EXACT = "exact"
    NORMALIZED = "normalized"
    UNMATCHED = "unmatched"


class RequirementPriority(str, enum.Enum):
    MUST_HAVE = "must_have"
    PREFERRED = "preferred"


class RequirementCategory(str, enum.Enum):
    SKILL = "skill"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    RESPONSIBILITY = "responsibility"


class MatchLevel(str, enum.Enum):
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"
    NOT_DEMONSTRATED = "not_demonstrated"


class LLMStatus(str, enum.Enum):
    SUCCESS = "success"
    FALLBACK = "fallback"  # LLM failed; deterministic-only score used
    FAILED = "failed"
