"""Rules that turn a matched phrase into an assertion about a particular.

A rule says four things beyond its pattern. Which particular it speaks to, in
which direction, whether what it describes is a permanent feature of the
premises or something that was true for a week, and how much weight it carries
on its own.

The persistence is the one that earns its place. A guest writing that there is
no lift contradicts a licence that claims one, permanently. A guest writing that
the lift was out of order contradicts the same particular for the length of
their stay and no longer, so it needs company before it is worth an inspection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from tariffpeg.claims.grammar import Pattern, compile_pattern, tokens_of
from tariffpeg.errors import Invalid
from tariffpeg.model.particulars import ClaimKind, spec_for

MAX_STRENGTH = 5
"""The heaviest a single rule is allowed to be on its own."""


class Polarity(StrEnum):
    """Which way a matched phrase points."""

    AFFIRMS = "affirms"
    DENIES = "denies"
    STATES = "states"


class Persistence(StrEnum):
    """Whether what was described is a feature or an incident."""

    STRUCTURAL = "structural"
    TRANSIENT = "transient"


@dataclass(frozen=True, slots=True)
class ClaimRule:
    """One published rule."""

    rule_id: str
    claim_key: str
    pattern: str
    polarity: Polarity
    persistence: Persistence
    strength: int
    value_scale: int = 1
    note: str = ""

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise Invalid("rule_id", self.rule_id, "a rule needs an id to be cited by")
        spec = spec_for(self.claim_key)
        if not 1 <= self.strength <= MAX_STRENGTH:
            raise Invalid("strength", self.strength, f"a rule weighs one to {MAX_STRENGTH}")
        if self.value_scale < 1:
            raise Invalid("value_scale", self.value_scale, "a scale multiplies, it does not divide")
        compiled = compile_pattern(self.pattern)
        captures = any(type(term).__name__ == "Number" for term in compiled.terms)
        if self.polarity is Polarity.STATES:
            if spec.kind is ClaimKind.FLAG:
                raise Invalid("polarity", self.polarity, "a yes or no particular has no value")
            if not captures:
                raise Invalid("pattern", self.pattern, "a rule that states a value captures one")
        elif self.value_scale != 1:
            raise Invalid("value_scale", self.value_scale, "only a stated value is scaled")
        elif captures:
            raise Invalid("pattern", self.pattern, "only a rule that states a value captures one")
        if spec.kind is not ClaimKind.FLAG and self.polarity is not Polarity.STATES:
            raise Invalid(
                "polarity", self.polarity, "a measured particular is contradicted by a value"
            )

    def compiled(self) -> Pattern:
        """Return the compiled pattern for this rule."""
        return compile_pattern(self.pattern)


@dataclass(frozen=True, slots=True)
class Assertion:
    """What one rule found in one review body."""

    rule_id: str
    claim_key: str
    polarity: Polarity
    persistence: Persistence
    strength: int
    quote: str
    value: int | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.strength <= MAX_STRENGTH:
            raise Invalid("strength", self.strength, f"an assertion weighs one to {MAX_STRENGTH}")

    @property
    def structural(self) -> bool:
        """Return whether this describes a feature rather than an incident."""
        return self.persistence is Persistence.STRUCTURAL


@dataclass(frozen=True, slots=True)
class RulePack:
    """A published set of rules, checked when it is built."""

    version: int
    rules: tuple[ClaimRule, ...]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise Invalid("version", self.version, "rule pack versions start at one")
        if not self.rules:
            raise Invalid("rules", 0, "a rule pack with no rules in it reads nothing")
        seen: set[str] = set()
        for rule in self.rules:
            if rule.rule_id in seen:
                raise Invalid("rule_id", rule.rule_id, "a rule id appears once in a pack")
            seen.add(rule.rule_id)

    def rule(self, rule_id: str) -> ClaimRule:
        """Return a rule by id, or refuse."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        raise Invalid("rule_id", rule_id, "this pack has no such rule")

    def for_claim(self, claim_key: str) -> tuple[ClaimRule, ...]:
        """Return the rules that speak to one particular."""
        return tuple(rule for rule in self.rules if rule.claim_key == claim_key)

    def claim_keys(self) -> tuple[str, ...]:
        """Return the particulars this pack has anything to say about."""
        return tuple(sorted({rule.claim_key for rule in self.rules}))

    def read(self, text: str) -> tuple[Assertion, ...]:
        """Return every assertion the rules find in a piece of text.

        A rule that matches twice in one review still asserts once. A guest who
        mentions the lift in two sentences is one guest.
        """
        tokens = tokens_of(text)
        found: list[Assertion] = []
        for rule in self.rules:
            hit = rule.compiled().find(text)
            if hit is None:
                continue
            found.append(
                Assertion(
                    rule_id=rule.rule_id,
                    claim_key=rule.claim_key,
                    polarity=rule.polarity,
                    persistence=rule.persistence,
                    strength=rule.strength,
                    quote=hit.span(tokens),
                    value=hit.numbers[0] * rule.value_scale if hit.numbers else None,
                )
            )
        return tuple(found)
