"""Noticing when a channel scoring has moved out from under its anchor table.

The anchors were agreed with each channel and they are the reason a score on one
dial can be set beside a score on another. If a channel changes how it prompts
for a rating, or starts hiding the low end, the table stops describing anything
and every comparison this package makes on that channel quietly tilts.

What is watched is the median, not the mean. A channel that starts dropping its
worst reviews moves the median, and the mean moves too but so does it when one
guest writes a very long complaint.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from tariffpeg.errors import Invalid
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review

LEAST_REVIEWS = 20
"""Below this a window says nothing about a channel and is not compared."""

TOLERANCE = 6
"""How far the median may move on the unit scale before the table is doubted."""


class Calibration(StrEnum):
    """What the two windows say about a channel."""

    HOLDS = "holds"
    THIN = "thin"
    DRIFTED = "drifted"


@dataclass(frozen=True, slots=True)
class Window:
    """What one channel looked like over one span of stay months."""

    channel: str
    first: StayMonth
    last: StayMonth
    count: int
    median_points: int

    @property
    def thin(self) -> bool:
        """Return whether there is too little here to say anything."""
        return self.count < LEAST_REVIEWS


@dataclass(frozen=True, slots=True)
class Drift:
    """What the comparison of two windows found."""

    channel: str
    earlier: Window
    later: Window
    verdict: Calibration

    @property
    def shift(self) -> int:
        """Return how far the median moved, which may be negative."""
        return self.later.median_points - self.earlier.median_points

    def line(self) -> str:
        """Return the line the report prints."""
        if self.verdict is Calibration.THIN:
            return (
                f"{self.channel}: too few reviews to say"
                f" ({self.earlier.count} then {self.later.count})"
            )
        moved = f"{self.shift:+d} points"
        if self.verdict is Calibration.HOLDS:
            return f"{self.channel}: the anchor table holds, the median moved {moved}"
        return (
            f"{self.channel}: the median moved {moved}, which is more than"
            f" {TOLERANCE}, so the anchor table wants agreeing again"
        )


def median_points(reviews: Sequence[Review]) -> int:
    """Return the middle score on the unit scale, or refuse an empty set."""
    if not reviews:
        raise Invalid("reviews", 0, "an empty set has no middle")
    ordered = sorted(review.unit_points for review in reviews)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) // 2


def window(channel: str, reviews: Sequence[Review], first: StayMonth, last: StayMonth) -> Window:
    """Return what one channel looked like across a span of stay months."""
    if last < first:
        raise Invalid("last", str(last), "a window ends after it starts")
    inside = [
        review for review in reviews if review.channel == channel and first <= review.stay <= last
    ]
    return Window(
        channel=channel,
        first=first,
        last=last,
        count=len(inside),
        median_points=median_points(inside) if inside else 0,
    )


def compare(earlier: Window, later: Window, tolerance: int = TOLERANCE) -> Drift:
    """Return what two windows say about whether the anchor table still holds."""
    if earlier.channel != later.channel:
        raise Invalid("channel", later.channel, "two windows of different channels do not compare")
    if tolerance < 0:
        raise Invalid("tolerance", tolerance, "a tolerance is not negative")
    if earlier.thin or later.thin:
        verdict = Calibration.THIN
    elif abs(later.median_points - earlier.median_points) > tolerance:
        verdict = Calibration.DRIFTED
    else:
        verdict = Calibration.HOLDS
    return Drift(earlier.channel, earlier, later, verdict)


def look_back(
    channel: str,
    reviews: Sequence[Review],
    at: StayMonth,
    months: int = 12,
    tolerance: int = TOLERANCE,
) -> Drift:
    """Compare the last so many months against the so many before them."""
    if months < 1:
        raise Invalid("months", months, "a window is a month or more")
    later = window(channel, reviews, at.minus(months - 1), at)
    earlier = window(channel, reviews, at.minus(2 * months - 1), at.minus(months))
    return compare(earlier, later, tolerance)
