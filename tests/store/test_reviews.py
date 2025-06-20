"""The sample counts when the unit first had a review, not when it last looked."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import NotFound
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.model.review import Review
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.reviews import COLUMNS, ReviewStore, flatten
from tests.store.conftest import DIGEST, a_capture, a_channel

SEEN = dt.datetime(2025, 8, 1, 9, 0, tzinfo=dt.UTC)
BODY = "The lift was out for the whole week and nobody at the desk said a word."


def review(**over: object) -> Review:
    base: dict[str, object] = {
        "channel": "seaboard",
        "channel_review_id": "91188",
        "licence_serial": 4021,
        "stay": StayMonth(2025, 7),
        "unit_points": 74,
        "raw_score": "8.4",
        "body": BODY,
        "capture_digest": DIGEST,
        "profile_key": "seaboard/v1",
    }
    base.update(over)
    return Review(**base)  # type: ignore[arg-type]


def test_flattening_produces_one_value_for_every_column() -> None:
    assert len(flatten(review(), SEEN)) == len(COLUMNS)


def test_a_review_round_trips_through_the_store(stocked: Database) -> None:
    store = ReviewStore(stocked)
    original = review(
        title="Lovely spot",
        reviewer_initials="A. L.",
        room_class="twin-en-suite",
        language="fr",
        submitted=dt.date(2025, 8, 3),
        operator_response="The lift is fixed.",
    )
    assert store.add(original, SEEN)
    assert store.get(original.key) == original


def test_a_review_with_no_submission_date_round_trips_too(stocked: Database) -> None:
    store = ReviewStore(stocked)
    store.add(review(), SEEN)
    assert store.get("seaboard:91188").submitted is None


def test_a_review_is_reachable_the_way_its_own_channel_numbers_it(stocked: Database) -> None:
    store = ReviewStore(stocked)
    store.add(review(), SEEN)
    assert store.on_channel("seaboard", "91188").channel_review_id == "91188"


def test_seeing_a_review_again_leaves_the_first_seen_date_alone(stocked: Database) -> None:
    store = ReviewStore(stocked)
    store.add(review(), SEEN)
    later = SEEN + dt.timedelta(days=30)
    assert not store.add(review(unit_points=20), later)
    assert store.first_seen("seaboard:91188") == SEEN
    assert store.get("seaboard:91188").unit_points == 74


def test_asking_for_a_review_nobody_holds_is_refused(stocked: Database) -> None:
    store = ReviewStore(stocked)
    with pytest.raises(NotFound, match="review"):
        store.get("seaboard:99999")
    with pytest.raises(NotFound, match="review"):
        store.first_seen("seaboard:99999")


def test_reviews_for_a_licence_come_back_oldest_stay_first(stocked: Database) -> None:
    store = ReviewStore(stocked)
    for number, month in (("1", 9), ("2", 6), ("3", 7)):
        store.add(review(channel_review_id=number, stay=StayMonth(2025, month)), SEEN)
    assert [r.stay.month for r in store.for_licence(4021)] == [6, 7, 9]
    assert store.for_licence(9999) == ()


def test_reviews_can_be_asked_for_a_range_of_stay_months(stocked: Database) -> None:
    store = ReviewStore(stocked)
    for number, (year, month) in enumerate([(2024, 12), (2025, 6), (2025, 7), (2026, 1)]):
        store.add(review(channel_review_id=str(number), stay=StayMonth(year, month)), SEEN)
    found = store.between(4021, StayMonth(2025, 1), StayMonth(2025, 12))
    assert [str(r.stay) for r in found] == ["2025-06", "2025-07"]


def test_reviews_can_be_asked_for_a_channel(stocked: Database) -> None:
    ChannelStore(stocked).add(a_channel("quayside"))
    CaptureStore(stocked).record(a_capture("sha256:" + "b" * 64, "quayside"))
    store = ReviewStore(stocked)
    store.add(review(), SEEN)
    store.add(
        review(channel="quayside", capture_digest="sha256:" + "b" * 64),
        SEEN,
    )
    assert len(store.for_channel("seaboard")) == 1
    assert len(store.for_channel("quayside")) == 1
    assert store.channels_for(4021) == ("quayside", "seaboard")


def test_the_count_for_a_licence_is_what_is_held(stocked: Database) -> None:
    store = ReviewStore(stocked)
    assert store.count_for(4021) == 0
    store.add(review(), SEEN)
    store.add(review(channel_review_id="2"), SEEN)
    assert store.count_for(4021) == 2


def test_the_tally_by_month_counts_each_stay_month(stocked: Database) -> None:
    store = ReviewStore(stocked)
    for number, month in (("1", 7), ("2", 7), ("3", 2)):
        store.add(review(channel_review_id=number, stay=StayMonth(2025, month)), SEEN)
    tally = store.counts_by_month(4021)
    assert tally[StayMonth(2025, 7)] == 2
    assert tally[StayMonth(2025, 2)] == 1


def test_the_tally_by_season_rolls_the_months_up(stocked: Database) -> None:
    store = ReviewStore(stocked)
    for number, month in (("1", 7), ("2", 8), ("3", 6), ("4", 1)):
        store.add(review(channel_review_id=number, stay=StayMonth(2025, month)), SEEN)
    tally = store.counts_by_season(4021)
    assert tally[Season.PEAK] == 2
    assert tally[Season.SHOULDER] == 1
    assert tally[Season.OFF] == 1


def test_a_licence_with_no_reviews_still_tallies_every_season(stocked: Database) -> None:
    assert ReviewStore(stocked).counts_by_season(4021) == dict.fromkeys(Season, 0)


def test_the_reviews_read_out_of_one_capture_can_be_listed(stocked: Database) -> None:
    store = ReviewStore(stocked)
    store.add(review(), SEEN)
    store.add(review(channel_review_id="2"), SEEN)
    assert len(store.from_capture(DIGEST)) == 2
    assert store.from_capture("sha256:" + "f" * 64) == ()


def test_dropping_a_licence_takes_its_reviews_with_it(stocked: Database) -> None:
    store = ReviewStore(stocked)
    store.add(review(), SEEN)
    store.add(review(channel_review_id="2"), SEEN)
    assert store.remove_for_licence(4021) == 2
    assert store.count_for(4021) == 0
    assert store.remove_for_licence(4021) == 0


def test_a_review_pointing_at_a_capture_nobody_took_is_refused(stocked: Database) -> None:
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        ReviewStore(stocked).add(review(capture_digest="sha256:" + "f" * 64), SEEN)
