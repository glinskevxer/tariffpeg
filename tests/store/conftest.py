"""A store with a channel, a licence and a capture already in it."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.model.licence import Licence
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore

AGENT = "tariffpeg-harvester (standards@example-authority.test)"
DIGEST = "sha256:" + "a" * 64
FETCHED = dt.datetime(2025, 7, 4, 22, 15, tzinfo=dt.UTC)


def a_channel(slug: str = "seaboard") -> Channel:
    """Return a channel record for the tests to register."""
    return Channel(
        slug=slug,
        name=slug.title(),
        base_url=f"https://{slug}.example",
        syndication=SyndicationClass.PRIMARY,
        policy=FetchPolicy(AGENT, 1500, 400),
    )


def a_licence(serial: int = 4021) -> Licence:
    """Return a licence record for the tests to register."""
    return Licence(
        serial=serial,
        trading_name="The Anchor Rooms",
        operator_name="Pellow and Daughter",
        locality="Porthgwarra",
        period_start=dt.date(2025, 4, 1),
        period_end=dt.date(2026, 3, 31),
        particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18, "lift": True},
        closed_months=frozenset({1, 2}),
    )


def a_capture(digest: str = DIGEST, channel: str = "seaboard") -> Capture:
    """Return a capture record for the tests to register."""
    return Capture(
        digest=digest,
        channel=channel,
        url=f"https://{channel}.example/p/1/reviews",
        final_url=f"https://{channel}.example/p/1/reviews",
        status=200,
        fetched_at=FETCHED,
        byte_count=4096,
        profile_key=f"{channel}/v1",
        licence_serial=4021,
    )


@pytest.fixture
def stocked(db: Database) -> Database:
    """A store with one channel, one licence and one capture in it."""
    ChannelStore(db).add(a_channel())
    LicenceStore(db).add(a_licence())
    CaptureStore(db).record(a_capture())
    return db
