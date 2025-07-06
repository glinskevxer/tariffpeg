"""A review syndicated onto four channels is one review towards the sample."""

from __future__ import annotations

from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.model.review import Review
from tariffpeg.sample.coverage import Coverage, SeasonCoverage, measure, window_for
from tariffpeg.sample.regime import PUBLISHED
from tests.sample.conftest import a_review

NOW = StayMonth(2026, 6)
SHARED = "The lift was out of order for the entire week and nobody said a word about it."


def peak(count: int, channel: str = "seaboard") -> list[Review]:
    return [a_review(f"{channel}-p{n}", 2025, 7, channel) for n in range(count)]


def test_a_licence_with_nothing_held_is_short_by_the_whole_requirement(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    found = measure(requirement, [], channels, NOW)
    assert found.total_shortfall == requirement.total
    assert found.channel_shortfall == requirement.minimum_channels
    assert not found.satisfied
    assert found.opinions == 0


def test_reviews_inside_the_window_count_towards_their_season(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    found = measure(requirement, peak(3), channels, NOW)
    assert found.season(Season.PEAK).held == 3
    assert found.season(Season.OFF).held == 0


def test_reviews_older_than_the_window_do_not_count(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    old = [a_review("old", 2019, 7)]
    found = measure(requirement, old, channels, NOW)
    assert found.season(Season.PEAK).held == 0


def test_reviews_of_another_licence_do_not_count(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    elsewhere = [a_review("x", 2025, 7, serial=9999)]
    assert measure(requirement, elsewhere, channels, NOW).opinions == 0


def test_the_window_runs_back_the_number_of_months_the_regime_says(
    anchor: Licence,
) -> None:
    requirement = PUBLISHED.require(anchor)
    start, end = window_for(requirement, NOW)
    assert end == NOW
    assert start == StayMonth(2024, 7)
    assert end.months_since(start) == requirement.lookback_months - 1


def test_a_syndicated_copy_counts_once(anchor: Licence, channels: dict[str, Channel]) -> None:
    requirement = PUBLISHED.require(anchor)
    reviews = [
        a_review("1", 2025, 7, "seaboard", SHARED),
        a_review("77", 2025, 7, "atlas", SHARED),
    ]
    found = measure(requirement, reviews, channels, NOW)
    assert found.opinions == 1
    assert found.season(Season.PEAK).held == 1


def test_an_aggregator_is_not_a_second_independent_channel(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    reviews = [
        a_review("1", 2025, 7, "seaboard", SHARED),
        a_review("77", 2025, 7, "atlas", SHARED),
    ]
    found = measure(requirement, reviews, channels, NOW)
    assert found.channels_held == ("seaboard",)
    assert found.channel_shortfall == 1


def test_two_channels_that_collect_their_own_satisfy_the_channel_requirement(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    reviews = [*peak(2, "seaboard"), *peak(2, "quayside")]
    found = measure(requirement, reviews, channels, NOW)
    assert found.channels_held == ("quayside", "seaboard")
    assert found.channel_shortfall == 0


def test_a_licence_with_enough_everywhere_is_satisfied(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    reviews: list[Review] = []
    for season_month, wanted in ((7, Season.PEAK), (5, Season.SHOULDER), (2, Season.OFF)):
        for n in range(requirement.wanted(wanted)):
            channel = "seaboard" if n % 2 else "quayside"
            reviews.append(a_review(f"{season_month}-{n}", 2025, season_month, channel))
    found = measure(requirement, reviews, channels, NOW)
    assert found.total_shortfall == 0
    assert found.satisfied


def test_the_seasons_still_short_come_back_worst_first(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    reviews = peak(requirement.wanted(Season.PEAK))
    found = measure(requirement, reviews, channels, NOW)
    short = found.short_seasons()
    assert Season.PEAK not in short
    assert short[0] is Season.SHOULDER


def test_a_season_that_is_over_sampled_is_not_short(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    found = measure(requirement, peak(requirement.wanted(Season.PEAK) + 5), channels, NOW)
    assert found.season(Season.PEAK).shortfall == 0
    assert found.season(Season.PEAK).satisfied


def test_the_statement_says_the_window_the_count_and_the_channels(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    requirement = PUBLISHED.require(anchor)
    lines = measure(requirement, peak(2), channels, NOW).statement()
    assert lines[0] == "window 2024-07 to 2026-06"
    assert lines[1] == "2 distinct opinions held"
    assert any("peak: 2 of" in line for line in lines)
    assert lines[-1].startswith("independent channels: seaboard")


def test_the_statement_says_none_when_no_channel_has_given_anything_up(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    lines = measure(PUBLISHED.require(anchor), [], channels, NOW).statement()
    assert lines[-1].startswith("independent channels: none")


def test_a_season_nobody_measured_reads_as_nothing_held_and_nothing_wanted() -> None:
    found = Coverage(4021, (), (), 2, (StayMonth(2025, 1), StayMonth(2026, 1)), 0)
    entry = found.season(Season.PEAK)
    assert entry.wanted == 0
    assert entry.held == 0
    assert entry.satisfied


def test_a_shortfall_is_never_negative() -> None:
    assert SeasonCoverage(Season.PEAK, 3, 9).shortfall == 0
    assert SeasonCoverage(Season.PEAK, 9, 3).shortfall == 6
