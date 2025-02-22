"""A channel carries the terms we agreed with it, and they are not negotiable at run time."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.channel import (
    ALWAYS,
    Channel,
    CourtesyWindow,
    FetchPolicy,
    SyndicationClass,
)

AGENT = "tariffpeg-harvester (standards@example-authority.test)"


def policy(**over: object) -> FetchPolicy:
    base: dict[str, object] = {
        "user_agent": AGENT,
        "crawl_delay_ms": 1500,
        "daily_request_ceiling": 400,
    }
    base.update(over)
    return FetchPolicy(**base)  # type: ignore[arg-type]


def test_a_window_that_does_not_wrap_holds_the_hours_between_its_ends() -> None:
    window = CourtesyWindow(9, 17)
    assert window.hours() == (9, 10, 11, 12, 13, 14, 15, 16)
    assert not window.wraps_midnight


def test_a_window_that_wraps_midnight_runs_through_the_small_hours() -> None:
    window = CourtesyWindow(22, 6)
    assert window.wraps_midnight
    assert window.hours() == (22, 23, 0, 1, 2, 3, 4, 5)


def test_an_hour_outside_the_clock_is_refused() -> None:
    with pytest.raises(Invalid, match="zero to twenty three"):
        CourtesyWindow(-1, 6)
    with pytest.raises(Invalid, match="zero to twenty three"):
        CourtesyWindow(9, 24)


def test_a_window_that_opens_and_closes_on_the_same_hour_is_refused() -> None:
    with pytest.raises(Invalid, match="not a window"):
        CourtesyWindow(9, 9)


def test_the_window_answers_whether_it_is_open_at_an_instant() -> None:
    window = CourtesyWindow(22, 6)
    assert window.is_open_at(dt.datetime(2025, 6, 1, 23, 30, tzinfo=dt.UTC))
    assert window.is_open_at(dt.datetime(2025, 6, 1, 5, 59, tzinfo=dt.UTC))
    assert not window.is_open_at(dt.datetime(2025, 6, 1, 6, 0, tzinfo=dt.UTC))
    assert not window.is_open_at(dt.datetime(2025, 6, 1, 12, 0, tzinfo=dt.UTC))


def test_an_instant_inside_the_window_is_its_own_next_opening() -> None:
    window = CourtesyWindow(22, 6)
    at = dt.datetime(2025, 6, 1, 23, 17, 42, tzinfo=dt.UTC)
    assert window.next_open(at) == at


def test_the_next_opening_lands_on_an_hour_boundary() -> None:
    window = CourtesyWindow(22, 6)
    at = dt.datetime(2025, 6, 1, 12, 17, 42, tzinfo=dt.UTC)
    assert window.next_open(at) == dt.datetime(2025, 6, 1, 22, 0, tzinfo=dt.UTC)


def test_the_next_opening_crosses_into_tomorrow_when_it_has_to() -> None:
    window = CourtesyWindow(9, 17)
    at = dt.datetime(2025, 6, 1, 18, 5, tzinfo=dt.UTC)
    assert window.next_open(at) == dt.datetime(2025, 6, 2, 9, 0, tzinfo=dt.UTC)


def test_the_default_window_leaves_one_hour_of_the_day_alone() -> None:
    assert len(ALWAYS.hours()) == 23
    assert 23 not in ALWAYS.hours()


def test_an_agent_string_without_a_contact_address_is_refused() -> None:
    with pytest.raises(Invalid, match="contact address"):
        policy(user_agent="tariffpeg-harvester")


def test_a_crawl_delay_under_the_floor_is_refused() -> None:
    with pytest.raises(Invalid, match="floor for any channel"):
        policy(crawl_delay_ms=100)
    assert policy(crawl_delay_ms=250).crawl_delay_ms == 250


def test_a_ceiling_or_a_page_limit_below_one_is_refused() -> None:
    with pytest.raises(Invalid, match="not reading"):
        policy(daily_request_ceiling=0)
    with pytest.raises(Invalid, match="not reading"):
        policy(max_pages_per_property=0)


def test_the_published_delay_wins_when_it_is_the_longer_one() -> None:
    assert policy().delay_with(4000) == 4000


def test_the_agreed_delay_wins_when_the_published_one_is_shorter() -> None:
    assert policy().delay_with(500) == 1500


def test_a_channel_with_no_published_delay_keeps_the_agreed_one() -> None:
    assert policy().delay_with(None) == 1500


def channel(**over: object) -> Channel:
    base: dict[str, object] = {
        "slug": "seaboard",
        "name": "Seaboard Stays",
        "base_url": "https://seaboard.example",
        "syndication": SyndicationClass.PRIMARY,
        "policy": policy(),
    }
    base.update(over)
    return Channel(**base)  # type: ignore[arg-type]


def test_a_channel_slug_has_to_already_be_a_slug() -> None:
    with pytest.raises(Invalid, match="hyphen separated"):
        channel(slug="Seaboard Stays")


def test_a_channel_needs_a_name_for_the_case_file() -> None:
    with pytest.raises(Invalid, match="needs a name"):
        channel(name="  ")


def test_channels_are_read_over_https_and_the_base_url_has_no_trailing_slash() -> None:
    with pytest.raises(Invalid, match="https only"):
        channel(base_url="http://seaboard.example")
    with pytest.raises(Invalid, match="trailing slash"):
        channel(base_url="https://seaboard.example/")


def test_only_a_primary_channel_carries_its_own_reviews() -> None:
    assert channel().carries_own_reviews
    assert not channel(syndication=SyndicationClass.AGGREGATOR).carries_own_reviews
    assert not channel(syndication=SyndicationClass.MIRROR).carries_own_reviews
