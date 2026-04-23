"""A review read by version two has to keep meaning what version two meant."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import AlreadyExists, Conflict, NotFound
from tariffpeg.model.profile import FieldRule, Profile
from tariffpeg.store.db import Database
from tariffpeg.store.profiles import ProfileStore

ON = dt.date(2026, 1, 5)
LATER = dt.date(2026, 6, 1)

FIELDS = (
    FieldRule("channel_review_id", "attribute", "article.review", "data-id", required=True),
    FieldRule("body", "text", "p.body", required=True),
    FieldRule("score", "structured", key="ratingValue", required=True),
)


def profile(version: int = 1, **over: object) -> Profile:
    base: dict[str, object] = {
        "channel": "seaboard",
        "version": version,
        "container": "article.review",
        "fields": FIELDS,
        "next_page": "a.next",
        "prefer_structured": True,
    }
    base.update(over)
    return Profile(**base)  # type: ignore[arg-type]


def test_a_profile_round_trips_through_the_store(stocked: Database) -> None:
    store = ProfileStore(stocked)
    original = profile()
    store.register(original, ON)
    assert store.get("seaboard", 1) == original


def test_the_fields_come_back_in_the_order_they_were_written(stocked: Database) -> None:
    store = ProfileStore(stocked)
    store.register(profile(), ON)
    assert store.get("seaboard", 1).field_names() == (
        "channel_review_id",
        "body",
        "score",
    )


def test_a_structured_field_keeps_its_key_and_no_selector(stocked: Database) -> None:
    store = ProfileStore(stocked)
    store.register(profile(), ON)
    rule = store.get("seaboard", 1).rule("score")
    assert rule is not None
    assert rule.source == "structured"
    assert rule.key == "ratingValue"
    assert rule.selector == ""


def test_registering_the_same_version_twice_is_refused(stocked: Database) -> None:
    store = ProfileStore(stocked)
    store.register(profile(), ON)
    with pytest.raises(AlreadyExists, match="profile"):
        store.register(profile(), ON)


def test_a_new_version_retires_the_one_that_was_live(stocked: Database) -> None:
    store = ProfileStore(stocked)
    store.register(profile(1), ON)
    store.register(profile(2), LATER)
    live = store.live("seaboard")
    assert live is not None
    assert live.version == 2
    assert store.retired_on("seaboard", 1) == LATER
    assert store.retired_on("seaboard", 2) is None


def test_a_version_earlier_than_the_live_one_is_refused(stocked: Database) -> None:
    store = ProfileStore(stocked)
    store.register(profile(3), ON)
    with pytest.raises(Conflict, match="is live and is later"):
        store.register(profile(2), LATER)


def test_a_channel_with_no_profile_has_nothing_live(stocked: Database) -> None:
    assert ProfileStore(stocked).live("seaboard") is None
    assert ProfileStore(stocked).versions("seaboard") == ()


def test_every_version_held_comes_back_oldest_first(stocked: Database) -> None:
    store = ProfileStore(stocked)
    store.register(profile(1), ON)
    store.register(profile(2), LATER)
    assert store.versions("seaboard") == (1, 2)


def test_asking_for_a_version_nobody_registered_is_refused(stocked: Database) -> None:
    store = ProfileStore(stocked)
    with pytest.raises(NotFound, match="profile"):
        store.get("seaboard", 9)
    with pytest.raises(NotFound, match="profile"):
        store.retired_on("seaboard", 9)


def test_the_live_profiles_come_back_by_channel(stocked: Database) -> None:
    store = ProfileStore(stocked)
    store.register(profile(), ON)
    found = store.live_by_channel(["seaboard", "quayside"])
    assert sorted(found) == ["seaboard"]
    assert found["seaboard"].version == 1


def test_a_retired_version_is_still_readable(stocked: Database) -> None:
    store = ProfileStore(stocked)
    store.register(profile(1), ON)
    store.register(profile(2, container="section.review"), LATER)
    assert store.get("seaboard", 1).container == "article.review"
    assert store.get("seaboard", 2).container == "section.review"


def test_a_profile_for_a_channel_nobody_registered_is_refused(db: Database) -> None:
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        ProfileStore(db).register(profile(), ON)


def test_a_field_row_reads_back_into_the_rule_it_came_from(stocked: Database) -> None:
    from tariffpeg.store.profiles import FIELD_COLUMNS, FIELD_SELECT, field_of

    store = ProfileStore(stocked)
    store.register(profile(), ON)
    row = stocked.conn.execute(
        f"{FIELD_SELECT} WHERE channel = ? AND version = ? AND name = ?",
        ("seaboard", 1, "body"),
    ).fetchone()
    assert len(FIELD_COLUMNS) == 9
    assert field_of(row) == FieldRule("body", "text", "p.body", required=True)
