"""
Deterministic skill normalization: maps a raw skill string (as
extracted verbatim from a resume or referenced in a JD requirement) to
a canonical name and a match type (exact / normalized / unmatched).

Pure and dependency-free by design (no DB, no LLM) so it is trivially
unit-testable and runs in microseconds -- this is the signature
"exact vs normalized vs related" distinction from the assignment brief,
and it must be deterministic and stable, never LLM-improvised.
"""
from dataclasses import dataclass

from app.models.enums import SkillMatchType
from app.services.skill_taxonomy import SKILL_ALIASES


@dataclass(frozen=True)
class NormalizedSkill:
    raw_text: str
    canonical_name: str
    match_type: SkillMatchType


class SkillNormalizer:
    """Wraps a canonical-name -> alias-list taxonomy into fast lookup
    tables. Instantiable with a custom taxonomy (useful for tests);
    `default_normalizer` below is the app-wide instance used in
    production."""

    def __init__(self, aliases: dict[str, list[str]]):
        self._canonical_by_lower: dict[str, str] = {
            canonical.lower(): canonical for canonical in aliases
        }
        self._alias_to_canonical: dict[str, str] = {}
        for canonical, alias_list in aliases.items():
            for alias in alias_list:
                key = alias.strip().lower()
                if key:
                    self._alias_to_canonical[key] = canonical

    def normalize(self, raw_text: str) -> NormalizedSkill:
        cleaned = raw_text.strip()
        lower = cleaned.lower()

        if lower in self._canonical_by_lower:
            return NormalizedSkill(
                raw_text=cleaned,
                canonical_name=self._canonical_by_lower[lower],
                match_type=SkillMatchType.EXACT,
            )

        if lower in self._alias_to_canonical:
            return NormalizedSkill(
                raw_text=cleaned,
                canonical_name=self._alias_to_canonical[lower],
                match_type=SkillMatchType.NORMALIZED,
            )

        return NormalizedSkill(
            raw_text=cleaned, canonical_name=cleaned, match_type=SkillMatchType.UNMATCHED
        )

    def normalize_many(self, raw_texts: list[str]) -> list[NormalizedSkill]:
        return [self.normalize(t) for t in raw_texts]

    def canonical_names_covered(self) -> set[str]:
        """Every canonical skill name this taxonomy recognizes -- used by
        the deterministic matcher to spot skill mentions inside free-text
        JD requirements."""
        return set(self._canonical_by_lower.values())


default_normalizer = SkillNormalizer(SKILL_ALIASES)


def normalize_skill(raw_text: str) -> NormalizedSkill:
    return default_normalizer.normalize(raw_text)
