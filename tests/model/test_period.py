"""Channels publish the month, never the day, so everything downstream works in months."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.period import (
    DEFAULT_SEASONS,
    Season,
    SeasonCalendar,
    StayMonth,
    month_number,
    month_range,
    parse_stay_month,
)


def test_a_stay_month_prints_as_a_year_and_a_padded_month() -> None:
    assert str(StayMonth(2025, 6)) == "2025-06"
    assert str(StayMonth(2025, 11)) == "2025-11"


def test_a_month_outside_the_calendar_is_refused() -> None:
    with pytest.raises(Invalid, match="one to twelve"):
        StayMonth(2025, 0)
    with pytest.raises(Invalid, match="one to twelve"):
        StayMonth(2025, 13)


def test_a_year_a_stay_could_not_have_happened_in_is_refused() -> None:
    with pytest.raises(Invalid, match="not a year"):
        StayMonth(1066, 6)


def test_stay_months_sort_in_calendar_order() -> None:
    months = [StayMonth(2026, 1), StayMonth(2025, 6), StayMonth(2025, 12)]
    assert sorted(months) == [StayMonth(2025, 6), StayMonth(2025, 12), StayMonth(2026, 1)]


def test_arithmetic_crosses_the_end_of_the_year() -> None:
    assert StayMonth(2025, 11).plus(3) == StayMonth(2026, 2)
    assert StayMonth(2025, 2).minus(3) == StayMonth(2024, 11)
    assert StayMonth(2025, 6).plus(0) == StayMonth(2025, 6)


def test_the_gap_between_two_months_counts_months() -> None:
    assert StayMonth(2026, 2).months_since(StayMonth(2025, 11)) == 3
    assert StayMonth(2025, 6).months_since(StayMonth(2025, 6)) == 0
    assert StayMonth(2025, 1).months_since(StayMonth(2025, 6)) == -5


def test_a_month_knows_its_first_and_last_day() -> None:
    assert StayMonth(2025, 6).first_day() == dt.date(2025, 6, 1)
    assert StayMonth(2025, 6).last_day() == dt.date(2025, 6, 30)
    assert StayMonth(2024, 2).last_day() == dt.date(2024, 2, 29)
    assert StayMonth(2025, 12).last_day() == dt.date(2025, 12, 31)


def test_a_date_falls_into_the_month_it_is_in() -> None:
    assert StayMonth.of(dt.date(2025, 6, 30)) == StayMonth(2025, 6)


def test_the_ordinal_round_trips() -> None:
    for month in (StayMonth(2025, 1), StayMonth(2025, 12), StayMonth(2026, 7)):
        assert StayMonth.from_ordinal(month.ordinal) == month


def test_an_iso_month_is_read() -> None:
    assert parse_stay_month("2025-06") == StayMonth(2025, 6)
    assert parse_stay_month("2025-6") == StayMonth(2025, 6)


def test_a_slashed_month_is_read_with_the_month_first() -> None:
    assert parse_stay_month("06/2025") == StayMonth(2025, 6)
    assert parse_stay_month("6/2025") == StayMonth(2025, 6)


def test_a_named_month_is_read_in_either_order() -> None:
    assert parse_stay_month("June 2025") == StayMonth(2025, 6)
    assert parse_stay_month("2025 June") == StayMonth(2025, 6)


def test_a_named_month_survives_the_punctuation_channels_add() -> None:
    assert parse_stay_month("Jun. 2025") == StayMonth(2025, 6)
    assert parse_stay_month("June, 2025") == StayMonth(2025, 6)
    assert parse_stay_month("  SEPT   2025 ") == StayMonth(2025, 9)


def test_a_blank_stay_month_is_refused() -> None:
    with pytest.raises(Invalid, match="carried no stay month"):
        parse_stay_month("   ")


def test_a_shape_the_reader_does_not_know_is_refused() -> None:
    with pytest.raises(Invalid, match="not a shape this reader knows"):
        parse_stay_month("last summer")
    with pytest.raises(Invalid, match="not a shape this reader knows"):
        parse_stay_month("30 June 2025")


def test_a_month_name_the_reader_does_not_know_is_refused() -> None:
    with pytest.raises(Invalid, match="not a month name"):
        parse_stay_month("Smarch 2025")
    with pytest.raises(Invalid, match="not a month name"):
        month_number("thermidor")


def test_a_month_name_is_read_in_full_or_abbreviated() -> None:
    assert month_number("January") == 1
    assert month_number("jan") == 1
    assert month_number("SEPT") == 9
    assert month_number("december") == 12


def test_the_default_calendar_puts_the_peak_where_the_order_puts_it() -> None:
    assert DEFAULT_SEASONS.season_of(7) is Season.PEAK
    assert DEFAULT_SEASONS.season_of(8) is Season.PEAK
    assert DEFAULT_SEASONS.season_of(6) is Season.SHOULDER
    assert DEFAULT_SEASONS.season_of(9) is Season.SHOULDER
    assert DEFAULT_SEASONS.season_of(1) is Season.OFF


def test_a_month_reports_its_own_season() -> None:
    assert StayMonth(2025, 8).season() is Season.PEAK
    assert StayMonth(2025, 2).season() is Season.OFF


def test_the_calendar_lists_the_months_in_each_season() -> None:
    assert DEFAULT_SEASONS.months_in(Season.PEAK) == (7, 8)
    assert DEFAULT_SEASONS.months_in(Season.SHOULDER) == (5, 6, 9, 10)
    assert DEFAULT_SEASONS.months_in(Season.OFF) == (1, 2, 3, 4, 11, 12)


def test_the_three_seasons_between_them_cover_the_year() -> None:
    covered = sum(len(DEFAULT_SEASONS.months_in(season)) for season in Season)
    assert covered == 12


def test_a_month_in_two_seasons_at_once_is_refused() -> None:
    with pytest.raises(Invalid, match="one season only"):
        SeasonCalendar(frozenset({7, 8}), frozenset({8, 9}))


def test_a_calendar_with_no_peak_is_refused() -> None:
    with pytest.raises(Invalid, match="has a peak in it"):
        SeasonCalendar(frozenset(), frozenset({5}))


def test_a_calendar_with_a_month_outside_the_year_is_refused() -> None:
    with pytest.raises(Invalid, match="one to twelve"):
        SeasonCalendar(frozenset({13}), frozenset())
    with pytest.raises(Invalid, match="one to twelve"):
        DEFAULT_SEASONS.season_of(0)


def test_a_range_of_months_covers_both_of_its_ends() -> None:
    span = month_range(StayMonth(2025, 11), StayMonth(2026, 2))
    assert [str(month) for month in span] == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert month_range(StayMonth(2025, 6), StayMonth(2025, 6)) == (StayMonth(2025, 6),)


def test_a_range_that_ends_before_it_starts_is_refused() -> None:
    with pytest.raises(Invalid, match="ends after it starts"):
        month_range(StayMonth(2026, 2), StayMonth(2025, 11))
