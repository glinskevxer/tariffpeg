"""A licence, a set of channels and a review builder the sampling tests share."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review

AGENT = "tariffpeg-harvester (standards@example-authority.test)"
DIGEST = "sha256:" + "a" * 64
WORDS = (
    "harbour quay slipway capstan bollard fender warp cleat mooring pontoon "
    "gangway ladder chandler lobster crab whelk mackerel pilchard seine drifter "
    "gig punt tender dinghy yawl ketch lugger trawler smack barge "
    "cove headland stack arch shingle boulder marram thrift samphire kelp "
    "granite slate serpentine gorse heather bracken foxglove campion sorrel"
).split()
"""A pool the bodies are drawn from, so that two unrelated reviews share no run
of words long enough to look like copies of each other."""


def a_channel(slug: str, syndication: SyndicationClass = SyndicationClass.PRIMARY) -> Channel:
    """Return a channel record."""
    return Channel(
        slug=slug,
        name=slug.title(),
        base_url=f"https://{slug}.example",
        syndication=syndication,
        policy=FetchPolicy(AGENT, 1500, 400),
    )


def a_review(
    number: str,
    year: int = 2025,
    month: int = 7,
    channel: str = "seaboard",
    body: str = "",
    serial: int = 4021,
) -> Review:
    """Return a review record with a body that is unique unless one is given."""
    return Review(
        channel=channel,
        channel_review_id=number,
        licence_serial=serial,
        stay=StayMonth(year, month),
        unit_points=74,
        raw_score="8.4",
        body=body or _body_for(number, channel),
        capture_digest=DIGEST,
        profile_key=f"{channel}/v1",
    )


def _body_for(number: str, channel: str) -> str:
    """Return a body that no other review in the suite comes close to."""
    seed = sum((position + 3) * ord(letter) for position, letter in enumerate(number + channel))
    step = 1 + seed % (len(WORDS) - 1)
    picked = [WORDS[(seed + step * n) % len(WORDS)] for n in range(16)]
    return " ".join(picked) + "."


@pytest.fixture
def channels() -> dict[str, Channel]:
    """Two channels that collect their own reviews and one that reproduces them."""
    return {
        "seaboard": a_channel("seaboard"),
        "quayside": a_channel("quayside"),
        "atlas": a_channel("atlas", SyndicationClass.AGGREGATOR),
    }


@pytest.fixture
def anchor() -> Licence:
    """A three key, nine room licence that trades all year."""
    return Licence(
        serial=4021,
        trading_name="The Anchor Rooms",
        operator_name="Pellow and Daughter",
        locality="Porthgwarra",
        period_start=dt.date(2025, 1, 1),
        period_end=dt.date(2026, 12, 31),
        particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18, "lift": True},
    )
