"""Whether a finding is spread across a premises or sits in one room class.

It changes what the inspector is sent to look at. Six guests saying the shower
runs cold, all of them in the attic twin, is a plumbing run on one floor. The
same six spread across every class is the boiler. The file cannot tell an
inspector which it is, but it can tell them which shape the evidence has.

A channel that does not publish a room class leaves this blank, and a finding
where most of the voices are blank is reported as such rather than as spread.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.model.review import Review
from tariffpeg.triage.corroborate import Finding

CONCENTRATION = 0.8
"""What share of the voices has to name one class before it is called concentrated."""

LEAST_VOICES = 3
"""Below this the shape of the evidence says nothing."""

UNKNOWN = "not given"
"""What a review with no room class on it counts as."""


@dataclass(frozen=True, slots=True)
class Spread:
    """How the voices behind one finding sit across the room classes."""

    claim_key: str
    counted: Mapping[str, int]
    voices: int

    @property
    def known(self) -> int:
        """Return how many voices named a room class at all."""
        return sum(count for name, count in self.counted.items() if name != UNKNOWN)

    @property
    def dominant(self) -> str:
        """Return the class with the most voices, or nothing if none named one."""
        named = {name: count for name, count in self.counted.items() if name != UNKNOWN}
        if not named:
            return ""
        return max(sorted(named), key=lambda name: named[name])

    @property
    def concentrated(self) -> bool:
        """Return whether nearly all the voices sit in one class."""
        if self.voices < LEAST_VOICES or not self.known:
            return False
        best = self.dominant
        return self.counted.get(best, 0) / self.known >= CONCENTRATION

    def line(self) -> str:
        """Return the line the case file prints about the shape of this finding."""
        if not self.known:
            return f"{self.claim_key}: no channel published a room class for any of these"
        if self.voices < LEAST_VOICES:
            return f"{self.claim_key}: too few voices to say how this sits across the rooms"
        if self.concentrated:
            share = self.counted[self.dominant] / self.known
            return (
                f"{self.claim_key}: {share:.0%} of the voices that named a room class"
                f" were in {self.dominant}"
            )
        listed = ", ".join(
            f"{name} {count}" for name, count in sorted(self.counted.items()) if name != UNKNOWN
        )
        return f"{self.claim_key}: spread across the classes, {listed}"


def spread(finding: Finding, reviews: Mapping[str, Review]) -> Spread:
    """Return how the voices behind a finding sit across the room classes."""
    counted: dict[str, int] = {}
    for item in finding.weighed:
        review = reviews.get(item.review_key)
        if review is None:
            continue
        name = review.room_class or UNKNOWN
        counted[name] = counted.get(name, 0) + 1
    return Spread(finding.claim_key, counted, sum(counted.values()))


def spreads(findings: Sequence[Finding], reviews: Mapping[str, Review]) -> tuple[Spread, ...]:
    """Return the shape of every finding, in the order they were given."""
    return tuple(spread(finding, reviews) for finding in findings)


def concentrated_only(found: Sequence[Spread]) -> tuple[Spread, ...]:
    """Return only the findings that sit in one room class."""
    return tuple(item for item in found if item.concentrated)


def share_in(found: Spread, room_class: str) -> float:
    """Return what share of the named voices sat in one class."""
    if not room_class.strip():
        raise Invalid("room_class", room_class, "a room class has a name")
    if not found.known:
        return 0.0
    return round(found.counted.get(room_class, 0) / found.known, 4)
