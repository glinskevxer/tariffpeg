"""How much one contradiction is worth by the time anybody looks at it.

Two things reduce weight and they reduce it at different rates. A guest saying
there is no lift is worth nearly as much two years later as it was on the day,
because a lift does not appear. A guest saying the lift was out of order is
worth very little two years later, because it was probably fixed the following
Tuesday. So the half life is per kind, not per contradiction.

Nothing decays to nothing. A floor is kept because a five year old report of a
missing lift is still a reason to look, just not a reason on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from tariffpeg.claims.contradiction import Contradiction
from tariffpeg.claims.rules import Persistence
from tariffpeg.errors import Invalid
from tariffpeg.model.period import StayMonth

HALF_LIFE_MONTHS = {Persistence.STRUCTURAL: 24, Persistence.TRANSIENT: 6}
"""How long it takes each kind to be worth half what it was."""

FLOOR = 0.15
"""What a contradiction is still worth however old it gets."""

PLACES = 4
"""Weights are rounded here so that two runs of the same evidence produce the
same number, whatever order the additions happened in."""


def half_life(persistence: Persistence) -> int:
    """Return the half life in months for a kind of contradiction."""
    try:
        return HALF_LIFE_MONTHS[persistence]
    except KeyError:
        raise Invalid(
            "persistence", persistence, "no half life is published for this kind"
        ) from None


def decay(months_old: int, persistence: Persistence) -> float:
    """Return the fraction of its weight a contradiction keeps at an age.

    An age before the stay is treated as no age at all. Channels do publish a
    stay month later than the month the review was written in, and a negative
    age would otherwise make a review worth more than it was on the day.
    """
    if months_old <= 0:
        return 1.0
    kept: float = 0.5 ** (months_old / half_life(persistence))
    return round(max(FLOOR, kept), PLACES)


@dataclass(frozen=True, slots=True)
class Weighed:
    """One contradiction and what it is worth now."""

    contradiction: Contradiction
    months_old: int
    weight: float

    @property
    def claim_key(self) -> str:
        """Return the particular this speaks to."""
        return self.contradiction.claim_key

    @property
    def review_key(self) -> str:
        """Return the review this came out of."""
        return self.contradiction.review_key

    @property
    def structural(self) -> bool:
        """Return whether this describes a feature rather than an incident."""
        return self.contradiction.structural

    def line(self) -> str:
        """Return the line a case file prints under the contradiction."""
        return f"{self.weight:.2f} after {self.months_old} months"


def weigh(contradiction: Contradiction, at: StayMonth) -> Weighed:
    """Return what a contradiction is worth at a given month."""
    months = at.months_since(contradiction.stay)
    kept = decay(months, contradiction.persistence)
    return Weighed(contradiction, months, round(contradiction.strength * kept, PLACES))


def weigh_all(found: tuple[Contradiction, ...], at: StayMonth) -> tuple[Weighed, ...]:
    """Return every contradiction weighed, heaviest first."""
    weighed = [weigh(item, at) for item in found]
    weighed.sort(key=lambda item: (-item.weight, item.review_key, item.claim_key))
    return tuple(weighed)
