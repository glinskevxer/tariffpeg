"""A channel that changes its templates does not send a notice."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.parse.dom import parse
from tariffpeg.parse.drift import DriftState, DriftWatch, Reading
from tariffpeg.parse.extract import extract
from tariffpeg.parse.profile import Profile

KEY = "seaboard/v1"


def feed(watch: DriftWatch, *readings: tuple[int, int, int]) -> None:
    for blocks, yielded, dropped in readings:
        watch.record(KEY, Reading("https://seaboard.example/p/1", blocks, yielded, dropped))


def test_a_profile_nobody_has_read_with_is_healthy() -> None:
    assert DriftWatch().state("nothing/v1") is DriftState.HEALTHY
    assert DriftWatch().reason("nothing/v1") == ""


def test_pages_that_give_up_reviews_keep_a_profile_healthy() -> None:
    watch = DriftWatch()
    feed(watch, (12, 12, 0), (12, 12, 0), (9, 9, 0))
    assert watch.state(KEY) is DriftState.HEALTHY
    assert watch.problems() == ()


def test_a_run_of_pages_with_no_blocks_marks_the_container_selector_gone() -> None:
    watch = DriftWatch()
    feed(watch, (12, 12, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0))
    assert watch.state(KEY) is DriftState.STALE
    assert "container selector is gone" in watch.reason(KEY)


def test_a_short_run_of_empty_pages_is_not_yet_stale() -> None:
    watch = DriftWatch()
    feed(watch, (12, 12, 0), (0, 0, 0), (0, 0, 0))
    assert watch.state(KEY) is DriftState.HEALTHY


def test_blocks_that_give_up_nothing_are_told_apart_from_no_blocks() -> None:
    watch = DriftWatch()
    feed(watch, (12, 0, 12), (12, 0, 12), (12, 0, 12))
    assert watch.state(KEY) is DriftState.STALE
    assert "no block gave up a required field" in watch.reason(KEY)


def test_a_high_drop_rate_across_the_window_is_worth_watching() -> None:
    watch = DriftWatch()
    feed(watch, (10, 4, 6), (10, 5, 5), (10, 6, 4))
    assert watch.state(KEY) is DriftState.WATCH
    assert "15 of 30 blocks dropped" in watch.reason(KEY)


def test_a_low_drop_rate_is_not_worth_watching() -> None:
    watch = DriftWatch()
    feed(watch, (10, 9, 1), (10, 10, 0), (10, 8, 2))
    assert watch.state(KEY) is DriftState.HEALTHY


def test_the_window_only_remembers_so_far_back() -> None:
    watch = DriftWatch(window=3)
    feed(watch, (10, 0, 10), (10, 0, 10), (10, 10, 0), (10, 10, 0), (10, 10, 0))
    assert len(watch.readings(KEY)) == 3
    assert watch.state(KEY) is DriftState.HEALTHY


def test_a_profile_recovers_once_the_pages_start_reading_again() -> None:
    watch = DriftWatch()
    feed(watch, (0, 0, 0), (0, 0, 0), (0, 0, 0))
    assert watch.state(KEY) is DriftState.STALE
    feed(watch, (10, 10, 0), (10, 10, 0), (10, 10, 0))
    assert watch.state(KEY) is DriftState.HEALTHY


def test_the_readings_come_back_oldest_first() -> None:
    watch = DriftWatch()
    feed(watch, (1, 1, 0), (2, 2, 0), (3, 3, 0))
    assert [reading.blocks_seen for reading in watch.readings(KEY)] == [1, 2, 3]


def test_a_new_profile_version_starts_the_count_again() -> None:
    watch = DriftWatch()
    feed(watch, (0, 0, 0), (0, 0, 0), (0, 0, 0))
    watch.forget(KEY)
    assert watch.readings(KEY) == ()
    assert watch.state(KEY) is DriftState.HEALTHY
    watch.forget("never-seen/v1")


def test_the_watch_lists_what_it_is_holding() -> None:
    watch = DriftWatch()
    watch.record("quayside/v2", Reading("u", 1, 1, 0))
    watch.record(KEY, Reading("u", 1, 1, 0))
    assert watch.watched() == ("quayside/v2", KEY)


def test_problems_name_the_profile_and_the_state() -> None:
    watch = DriftWatch()
    feed(watch, (0, 0, 0), (0, 0, 0), (0, 0, 0))
    watch.record("quayside/v2", Reading("u", 10, 10, 0))
    problems = watch.problems()
    assert len(problems) == 1
    assert problems[0].startswith("seaboard/v1 is stale:")


def test_a_reading_can_be_taken_straight_off_an_extraction(markup: str, profile: Profile) -> None:
    found = extract(profile, parse(markup))
    reading = Reading.of(found, "https://seaboard.example/p/1")
    assert reading.blocks_seen == 2
    assert reading.yielded == 2
    assert reading.dropped == 0
    assert reading.page_url.endswith("/p/1")


def test_a_watch_with_a_window_of_nothing_is_refused() -> None:
    with pytest.raises(Invalid, match="at least one reading"):
        DriftWatch(window=0)


def test_a_run_longer_than_the_window_is_refused() -> None:
    with pytest.raises(Invalid, match="never be reached"):
        DriftWatch(window=3, run_before_stale=4)


def test_a_run_of_nothing_and_a_rate_of_nothing_are_refused() -> None:
    with pytest.raises(Invalid, match="one reading or more"):
        DriftWatch(run_before_stale=0)
    with pytest.raises(Invalid, match="above nought"):
        DriftWatch(drop_rate_for_watch=0)
