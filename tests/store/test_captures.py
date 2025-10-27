"""The same bytes fetched twice keep the fetch time the case file quotes."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import NotFound
from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.store.captures import COLUMNS, CaptureStore, flatten
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database

AGENT = "tariffpeg-harvester (standards@example-authority.test)"
AT = dt.datetime(2025, 7, 4, 22, 15, tzinfo=dt.UTC)


def channel(slug: str = "seaboard") -> Channel:
    return Channel(
        slug=slug,
        name="Seaboard Stays",
        base_url=f"https://{slug}.example",
        syndication=SyndicationClass.PRIMARY,
        policy=FetchPolicy(AGENT, 1500, 400),
    )


def capture(**over: object) -> Capture:
    base: dict[str, object] = {
        "digest": "sha256:" + "a" * 64,
        "channel": "seaboard",
        "url": "https://seaboard.example/p/1/reviews",
        "final_url": "https://seaboard.example/p/1/reviews",
        "status": 200,
        "fetched_at": AT,
        "byte_count": 4096,
        "profile_key": "seaboard/v1",
        "licence_serial": 4021,
    }
    base.update(over)
    return Capture(**base)  # type: ignore[arg-type]


@pytest.fixture
def store(db: Database) -> CaptureStore:
    ChannelStore(db).add(channel())
    return CaptureStore(db)


def test_flattening_produces_one_value_for_every_column() -> None:
    assert len(flatten(capture())) == len(COLUMNS)


def test_a_capture_round_trips_through_the_store(store: CaptureStore) -> None:
    original = capture()
    assert store.record(original)
    assert store.get(original.digest) == original


def test_a_capture_with_no_licence_round_trips_too(store: CaptureStore) -> None:
    original = capture(licence_serial=None)
    store.record(original)
    assert store.get(original.digest).licence_serial is None


def test_recording_the_same_bytes_twice_keeps_the_first_fetch_time(
    store: CaptureStore,
) -> None:
    store.record(capture())
    assert not store.record(capture(fetched_at=AT + dt.timedelta(days=1)))
    assert store.get(capture().digest).fetched_at == AT
    assert store.count() == 1


def test_asking_for_a_capture_that_was_never_taken_is_refused(store: CaptureStore) -> None:
    with pytest.raises(NotFound, match="capture"):
        store.get("sha256:" + "f" * 64)


def test_captures_come_back_for_a_channel_oldest_first(db: Database) -> None:
    ChannelStore(db).add(channel())
    ChannelStore(db).add(channel("quayside"))
    store = CaptureStore(db)
    store.record(capture(digest="sha256:" + "b" * 64, fetched_at=AT + dt.timedelta(days=1)))
    store.record(capture(digest="sha256:" + "a" * 64))
    store.record(capture(digest="sha256:" + "c" * 64, channel="quayside"))
    found = store.for_channel("seaboard")
    assert [c.fetched_at for c in found] == [AT, AT + dt.timedelta(days=1)]


def test_captures_come_back_for_a_licence(store: CaptureStore) -> None:
    store.record(capture())
    store.record(capture(digest="sha256:" + "b" * 64, licence_serial=99))
    assert len(store.for_licence(4021)) == 1
    assert store.for_licence(1234) == ()


def test_the_latest_capture_of_a_url_is_the_most_recent_one(store: CaptureStore) -> None:
    store.record(capture())
    later = capture(digest="sha256:" + "b" * 64, fetched_at=AT + dt.timedelta(days=2))
    store.record(later)
    found = store.latest_for_url(capture().url)
    assert found is not None
    assert found.digest == later.digest
    assert store.latest_for_url("https://seaboard.example/nothing") is None


def test_the_daily_spend_counts_captures_on_one_utc_day(store: CaptureStore) -> None:
    store.record(capture())
    store.record(capture(digest="sha256:" + "b" * 64, fetched_at=AT + dt.timedelta(hours=1)))
    store.record(capture(digest="sha256:" + "c" * 64, fetched_at=AT + dt.timedelta(days=1)))
    assert store.spent_on("seaboard", dt.date(2025, 7, 4)) == 2
    assert store.spent_on("seaboard", dt.date(2025, 7, 5)) == 1
    assert store.spent_on("seaboard", dt.date(2025, 7, 6)) == 0


def test_a_capture_for_a_channel_that_is_not_registered_is_refused(db: Database) -> None:
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        CaptureStore(db).record(capture())
