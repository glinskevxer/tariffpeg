"""Setting what a guest said against what the operator signed for.

Three kinds of particular are compared three different ways and the third one is
the one that gets argued about. A flag is contradicted by its opposite. A count
is contradicted by a number outside the tolerance in either direction. A
distance is contradicted only when the guest puts it further away than the
licence does, because no operator has ever been called in over a beach that
turned out to be nearer than advertised.

A review too short to say anything carries no assertions at all. That gate is
here rather than in the rules, because a two word review can still match a rule
by accident and the fix is not to make the rules longer.
"""

from __future__ import annotations

from dataclasses import dataclass

from tariffpeg.claims.rules import Assertion, Persistence, Polarity, RulePack
from tariffpeg.model.licence import Licence
from tariffpeg.model.particulars import ClaimKind, spec_for
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review


@dataclass(frozen=True, slots=True)
class Contradiction:
    """One review saying something a licence does not."""

    review_key: str
    licence_serial: int
    claim_key: str
    rule_id: str
    persistence: Persistence
    strength: int
    quote: str
    stay: StayMonth
    declared: str
    asserted: str
    translated_from: str = ""

    @property
    def translated(self) -> bool:
        """Return whether these were the words a machine chose."""
        return bool(self.translated_from)

    @property
    def structural(self) -> bool:
        """Return whether this describes a feature rather than an incident."""
        return self.persistence is Persistence.STRUCTURAL

    def line(self) -> str:
        """Return the one line a case file prints for this contradiction."""
        spec = spec_for(self.claim_key)
        through = f", through a translation from {self.translated_from}" if self.translated else ""
        return (
            f"{self.claim_key}: the licence says {self.declared},"
            f" a guest in {self.stay} said {self.asserted}{through}"
            f" ({spec.label})"
        )


def _flag_contradicts(declared: bool, assertion: Assertion) -> bool:
    if assertion.polarity is Polarity.DENIES:
        return declared
    if assertion.polarity is Polarity.AFFIRMS:
        return not declared
    return False


def _value_contradicts(claim_key: str, declared: int, stated: int) -> bool:
    spec = spec_for(claim_key)
    if spec.upper_only:
        return stated > declared + spec.tolerance
    return abs(stated - declared) > spec.tolerance


def _asserted_text(claim_key: str, assertion: Assertion) -> str:
    spec = spec_for(claim_key)
    if assertion.polarity is Polarity.STATES and assertion.value is not None:
        return spec.render(assertion.value)
    return "no" if assertion.polarity is Polarity.DENIES else "yes"


def contradicts(licence: Licence, assertion: Assertion) -> bool:
    """Return whether one assertion runs against what the licence declares."""
    if not licence.declares(assertion.claim_key):
        return False
    spec = spec_for(assertion.claim_key)
    declared = licence.particular(assertion.claim_key)
    if spec.kind is ClaimKind.FLAG:
        assert isinstance(declared, bool)
        return _flag_contradicts(declared, assertion)
    if assertion.polarity is not Polarity.STATES or assertion.value is None:
        return False
    assert isinstance(declared, int)
    return _value_contradicts(assertion.claim_key, declared, assertion.value)


def read_review(review: Review, licence: Licence, pack: RulePack) -> tuple[Contradiction, ...]:
    """Return every contradiction one review raises against one licence."""
    if not review.is_substantial():
        return ()
    found: list[Contradiction] = []
    for assertion in pack.read(review.body):
        if not contradicts(licence, assertion):
            continue
        spec = spec_for(assertion.claim_key)
        found.append(
            Contradiction(
                review_key=review.key,
                licence_serial=licence.serial,
                claim_key=assertion.claim_key,
                rule_id=assertion.rule_id,
                persistence=assertion.persistence,
                strength=assertion.strength,
                quote=assertion.quote,
                stay=review.stay,
                declared=spec.render(licence.particular(assertion.claim_key)),
                asserted=_asserted_text(assertion.claim_key, assertion),
                translated_from=review.translated_from,
            )
        )
    return tuple(found)


def read_all(
    reviews: tuple[Review, ...], licence: Licence, pack: RulePack
) -> tuple[Contradiction, ...]:
    """Return every contradiction a set of reviews raises, in review order."""
    found: list[Contradiction] = []
    for review in sorted(reviews, key=lambda item: item.key):
        found.extend(read_review(review, licence, pack))
    return tuple(found)


def by_claim(found: tuple[Contradiction, ...]) -> dict[str, tuple[Contradiction, ...]]:
    """Group contradictions by the particular they speak to."""
    grouped: dict[str, list[Contradiction]] = {}
    for item in found:
        grouped.setdefault(item.claim_key, []).append(item)
    return {key: tuple(items) for key, items in sorted(grouped.items())}
