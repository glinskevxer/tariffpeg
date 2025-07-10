"""Fixtures every layer of the suite leans on.

The channels, the licence and the review builder live here rather than beside
the sampling tests, because the harvest tests need the same three and a fixture
that only one package can see gets copied into the next one.

The store fixture closes the connection on the way out. Warnings are errors in
this suite, and a connection that falls out of scope unclosed is a warning on
some interpreters and silence on others, which is the worst of both.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import pytest

from tariffpeg.clock import FixedClock
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review
from tariffpeg.store.db import Database
from tariffpeg.store.migrations import migrate

STARTED = dt.datetime(2025, 6, 12, 9, 0, tzinfo=dt.UTC)
"""Where every fixed clock in the suite starts, unless a test moves it."""


@pytest.fixture
def clock() -> FixedClock:
    """A clock parked in the middle of a trading season."""
    return FixedClock(STARTED)


@pytest.fixture
def db(clock: FixedClock) -> Iterator[Database]:
    """A migrated store in memory, closed when the test finishes."""
    store = Database()
    migrate(store, clock)
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def file_db(tmp_path: Path, clock: FixedClock) -> Iterator[Database]:
    """A migrated store on disk, for the tests that care that it is a file."""
    store = Database(tmp_path / "evidence.sqlite3")
    migrate(store, clock)
    try:
        yield store
    finally:
        store.close()


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
