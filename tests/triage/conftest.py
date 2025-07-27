"""Reviews and contradictions the triage tests build findings out of."""

from __future__ import annotations

import pytest

from tariffpeg.claims.contradiction import Contradiction, read_all
from tariffpeg.claims.pack import PACK
from tariffpeg.claims.rules import Persistence
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review
from tariffpeg.triage.weight import Weighed

DIGEST = "sha256:" + "a" * 64
NO_LIFT = "There is no lift at all and we were carried up three flights of stairs."
NO_LIFT_AGAIN = "They have no lift in the place, which nobody mentioned when we booked."
BROKEN_LIFT = "The lift was out of order for the whole week we stayed there."
BREAKFAST = "Breakfast was charged at twelve pounds a head on every single morning."


def a_review(number: str, body: str, channel: str = "seaboard", month: int = 7) -> Review:
    """Return a review carrying a given body."""
    return Review(
        channel=channel,
        channel_review_id=number,
        licence_serial=4021,
        stay=StayMonth(2025, month),
        unit_points=74,
        raw_score="8.4",
        body=body,
        capture_digest=DIGEST,
        profile_key=f"{channel}/v1",
    )


def contradictions(reviews: tuple[Review, ...], licence: Licence) -> tuple[Contradiction, ...]:
    """Return the contradictions a set of reviews raises."""
    return read_all(reviews, licence, PACK)


def a_weighed(
    claim_key: str = "lift",
    review_key: str = "seaboard:1",
    weight: float = 5.0,
    persistence: Persistence = Persistence.STRUCTURAL,
) -> Weighed:
    """Return a weighed contradiction without going through the rules."""
    return Weighed(
        Contradiction(
            review_key=review_key,
            licence_serial=4021,
            claim_key=claim_key,
            rule_id="lift-absent",
            persistence=persistence,
            strength=5,
            quote="there is no lift",
            stay=StayMonth(2025, 7),
            declared="yes",
            asserted="no",
        ),
        0,
        weight,
    )


@pytest.fixture
def at() -> StayMonth:
    """The month the triage tests decide at."""
    return StayMonth(2025, 9)
