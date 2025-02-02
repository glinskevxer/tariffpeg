"""Nothing decides anything against the wall clock, so the clock has to be movable."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.clock import (
    FixedClock,
    SystemClock,
    isoformat,
    parse_instant,
    require_utc,
    to_utc,
)


def test_the_system_clock_returns_an_aware_utc_instant() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == dt.timedelta(0)


def test_a_fixed_clock_stays_where_it_was_put() -> None:
    at = dt.datetime(2025, 6, 1, 9, 30, tzinfo=dt.UTC)
    clock = FixedClock(at)
    assert clock.now() == at
    assert clock.now() == at


def test_a_fixed_clock_moves_forward_by_the_delta_it_is_given() -> None:
    clock = FixedClock(dt.datetime(2025, 6, 1, 9, 30, tzinfo=dt.UTC))
    moved = clock.advance(hours=2, minutes=15)
    assert moved == dt.datetime(2025, 6, 1, 11, 45, tzinfo=dt.UTC)
    assert clock.now() == moved


def test_a_fixed_clock_can_be_moved_backwards_for_an_out_of_order_capture() -> None:
    clock = FixedClock(dt.datetime(2025, 6, 1, 9, 30, tzinfo=dt.UTC))
    clock.advance(days=-1)
    assert clock.now() == dt.datetime(2025, 5, 31, 9, 30, tzinfo=dt.UTC)


def test_a_fixed_clock_can_be_parked_somewhere_new() -> None:
    clock = FixedClock(dt.datetime(2025, 6, 1, tzinfo=dt.UTC))
    clock.set(dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    assert clock.now().year == 2026


def test_a_fixed_clock_refuses_a_naive_instant_at_both_doors() -> None:
    with pytest.raises(ValueError, match="no timezone"):
        FixedClock(dt.datetime(2025, 6, 1))
    clock = FixedClock(dt.datetime(2025, 6, 1, tzinfo=dt.UTC))
    with pytest.raises(ValueError, match="no timezone"):
        clock.set(dt.datetime(2025, 6, 2))


def test_a_non_utc_offset_is_refused_rather_than_shifted() -> None:
    at_one = dt.timezone(dt.timedelta(hours=1))
    with pytest.raises(ValueError, match="not in UTC"):
        require_utc(dt.datetime(2025, 6, 1, tzinfo=at_one), "at")


def test_converting_to_utc_keeps_the_instant_and_moves_the_offset() -> None:
    at_one = dt.timezone(dt.timedelta(hours=1))
    local = dt.datetime(2025, 6, 1, 10, 0, tzinfo=at_one)
    assert to_utc(local) == dt.datetime(2025, 6, 1, 9, 0, tzinfo=dt.UTC)


def test_a_naive_datetime_cannot_be_converted_because_its_offset_is_unknown() -> None:
    with pytest.raises(ValueError, match="offset is unknown"):
        to_utc(dt.datetime(2025, 6, 1, 10, 0))


def test_the_written_form_is_seconds_resolution_and_ends_in_z() -> None:
    at = dt.datetime(2025, 6, 1, 9, 30, 15, 987654, tzinfo=dt.UTC)
    assert isoformat(at) == "2025-06-01T09:30:15Z"


def test_the_written_form_reads_back_to_the_same_second() -> None:
    at = dt.datetime(2025, 6, 1, 9, 30, 15, tzinfo=dt.UTC)
    assert parse_instant(isoformat(at)) == at


def test_reading_back_accepts_an_explicit_offset_and_normalises_it() -> None:
    assert parse_instant("2025-06-01T10:30:15+01:00") == dt.datetime(
        2025, 6, 1, 9, 30, 15, tzinfo=dt.UTC
    )


def test_reading_back_refuses_a_stamp_with_no_offset() -> None:
    with pytest.raises(ValueError, match="does not carry an offset"):
        parse_instant("2025-06-01T09:30:15")


def test_written_stamps_sort_as_text_in_the_same_order_as_instants() -> None:
    base = dt.datetime(2025, 6, 1, tzinfo=dt.UTC)
    stamps = [isoformat(base + dt.timedelta(hours=h)) for h in (0, 5, 11, 23, 25, 400)]
    assert stamps == sorted(stamps)
