"""A premises that shuts for the winter cannot produce winter reviews."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import Season, SeasonCalendar
from tariffpeg.sample.regime import PUBLISHED, Regime, Requirement


def licence(
    particulars: dict[str, int] | None = None,
    closed_months: frozenset[int] = frozenset(),
) -> Licence:
    declared: dict[str, bool | int] = {"grading_band": 3, "let_rooms": 9, "bed_spaces": 18}
    declared.update(particulars or {})
    return Licence(
        serial=4021,
        trading_name="The Anchor Rooms",
        operator_name="Pellow and Daughter",
        locality="Porthgwarra",
        period_start=dt.date(2025, 4, 1),
        period_end=dt.date(2026, 3, 31),
        particulars=declared,
        closed_months=closed_months,
    )


def test_the_peak_is_sampled_harder_than_the_off_season() -> None:
    wanted = PUBLISHED.require(licence()).per_season
    assert wanted[Season.PEAK] > wanted[Season.SHOULDER] > wanted[Season.OFF]


def test_a_higher_grading_band_is_sampled_harder() -> None:
    two = PUBLISHED.require(licence({"grading_band": 2})).total
    five = PUBLISHED.require(licence({"grading_band": 5})).total
    assert five > two


def test_the_first_two_bands_are_sampled_the_same() -> None:
    one = PUBLISHED.require(licence({"grading_band": 1})).total
    two = PUBLISHED.require(licence({"grading_band": 2})).total
    assert one == two


def test_a_bigger_premises_is_sampled_harder() -> None:
    small = PUBLISHED.require(licence({"let_rooms": 4})).total
    large = PUBLISHED.require(licence({"let_rooms": 42})).total
    assert large > small


def test_the_size_multiplier_steps_every_ten_rooms() -> None:
    assert PUBLISHED.size_factor(1) == 1
    assert PUBLISHED.size_factor(10) == 1
    assert PUBLISHED.size_factor(11) == 2
    assert PUBLISHED.size_factor(20) == 2
    assert PUBLISHED.size_factor(21) == 3


def test_a_premises_that_lets_no_rooms_is_refused() -> None:
    with pytest.raises(Invalid, match="at least one room"):
        PUBLISHED.size_factor(0)


def test_a_band_the_regime_has_no_factor_for_is_refused() -> None:
    with pytest.raises(Invalid, match="no factor for this band"):
        PUBLISHED.band_factor(9)


def test_a_season_the_premises_is_shut_for_is_not_sampled_at_all() -> None:
    shut_in_winter = licence(closed_months=frozenset({1, 2, 3, 4, 11, 12}))
    wanted = PUBLISHED.require(shut_in_winter)
    assert wanted.wanted(Season.OFF) == 0
    assert wanted.wanted(Season.PEAK) > 0


def test_a_season_the_premises_is_half_shut_for_is_half_sampled() -> None:
    half = licence(closed_months=frozenset({5, 6}))
    full = PUBLISHED.wanted(licence(), Season.SHOULDER)
    assert PUBLISHED.wanted(half, Season.SHOULDER) < full
    assert PUBLISHED.wanted(half, Season.SHOULDER) > 0


def test_the_share_a_premises_is_open_for_is_reported_as_a_fraction() -> None:
    assert PUBLISHED.open_share(licence(), Season.PEAK) == 1.0
    shut = licence(closed_months=frozenset({7, 8}))
    assert PUBLISHED.open_share(shut, Season.PEAK) == 0.0
    half = licence(closed_months=frozenset({7}))
    assert PUBLISHED.open_share(half, Season.PEAK) == 0.5


def test_the_requirement_names_the_licence_it_is_for() -> None:
    assert PUBLISHED.require(licence()).serial == 4021


def test_the_requirement_totals_across_the_seasons() -> None:
    wanted = PUBLISHED.require(licence())
    assert wanted.total == sum(wanted.per_season.values())


def test_the_requirement_asks_for_more_than_one_channel() -> None:
    assert PUBLISHED.require(licence()).minimum_channels >= 2


def test_the_requirement_explains_itself_a_season_at_a_time() -> None:
    lines = PUBLISHED.require(licence(closed_months=frozenset({1, 2, 3, 4, 11, 12}))).explain()
    assert any("the premises is shut" in line for line in lines)
    assert any("peak" in line for line in lines)
    assert lines[-1].startswith("across at least")


def test_a_season_nobody_asked_about_wants_nothing() -> None:
    requirement = Requirement(4021, {Season.PEAK: 8}, 2, 24)
    assert requirement.wanted(Season.OFF) == 0
    assert requirement.total == 8


def test_a_regime_missing_a_season_is_refused() -> None:
    with pytest.raises(Invalid, match="quota for every season"):
        Regime(1, {Season.PEAK: 8})


def test_a_negative_quota_is_refused() -> None:
    with pytest.raises(Invalid, match="not negative"):
        Regime(1, {Season.PEAK: -1, Season.SHOULDER: 5, Season.OFF: 3})


def test_a_regime_below_one_channel_or_one_month_is_refused() -> None:
    quotas = {Season.PEAK: 8, Season.SHOULDER: 5, Season.OFF: 3}
    with pytest.raises(Invalid, match="needs one channel"):
        Regime(1, quotas, minimum_channels=0)
    with pytest.raises(Invalid, match="a month or more"):
        Regime(1, quotas, lookback_months=0)


def test_a_regime_version_below_one_is_refused() -> None:
    with pytest.raises(Invalid, match="start at one"):
        Regime(0)


def test_the_published_regime_carries_a_version_a_case_file_can_cite() -> None:
    assert PUBLISHED.version == 1
    assert PUBLISHED.lookback_months == 24


def test_a_season_the_calendar_gives_no_months_to_is_open_for_none_of_it() -> None:
    no_off_season = SeasonCalendar(frozenset({7, 8}), frozenset({1, 2, 3, 4, 5, 6, 9, 10, 11, 12}))
    regime = Regime(1, calendar=no_off_season)
    assert regime.open_share(licence(), Season.OFF) == 0.0
