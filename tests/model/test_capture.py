"""A capture is the record that answers for a quotation."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.capture import Capture

AT = dt.datetime(2025, 7, 4, 22, 15, tzinfo=dt.UTC)


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


def test_a_capture_is_named_by_its_digest() -> None:
    with pytest.raises(Invalid, match="content digest"):
        capture(digest="deadbeef")


def test_a_capture_belongs_to_a_channel_slug() -> None:
    with pytest.raises(Invalid, match="channel slug"):
        capture(channel="Seaboard Stays")


def test_a_capture_is_of_a_page_fetched_over_https() -> None:
    with pytest.raises(Invalid, match="over https"):
        capture(url="http://seaboard.example/p/1")
    with pytest.raises(Invalid, match="over https"):
        capture(final_url="http://seaboard.example/p/1")


def test_a_status_outside_the_range_is_refused() -> None:
    with pytest.raises(Invalid, match="not an http status"):
        capture(status=99)
    with pytest.raises(Invalid, match="not an http status"):
        capture(status=600)


def test_negative_bytes_or_negative_time_are_refused() -> None:
    with pytest.raises(Invalid, match="negative bytes"):
        capture(byte_count=-1)
    with pytest.raises(Invalid, match="negative time"):
        capture(elapsed_ms=-1)


def test_a_naive_fetch_time_is_refused() -> None:
    with pytest.raises(ValueError, match="no timezone"):
        capture(fetched_at=dt.datetime(2025, 7, 4, 22, 15))


def test_a_redirected_capture_says_so() -> None:
    assert not capture().redirected
    assert capture(final_url="https://seaboard.example/p/1/reviews?page=1").redirected


def test_a_capture_worth_reading_is_the_one_with_a_page_in_it() -> None:
    assert capture().usable
    assert not capture(status=404, byte_count=0).usable
    assert not capture(byte_count=0).usable
    assert not capture(status=304, byte_count=0).usable


def test_the_age_of_a_capture_is_measured_from_when_it_was_taken() -> None:
    assert capture().age_at(AT + dt.timedelta(days=3)) == dt.timedelta(days=3)
    assert capture().age_at(AT) == dt.timedelta(0)


def test_the_age_is_asked_for_in_utc() -> None:
    with pytest.raises(ValueError, match="no timezone"):
        capture().age_at(dt.datetime(2025, 7, 7))


def test_a_capture_with_no_licence_is_allowed_because_robots_files_have_none() -> None:
    assert capture(licence_serial=None).licence_serial is None
