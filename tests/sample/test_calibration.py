"""If the table stops describing anything, every comparison quietly tilts."""

from __future__ import annotations

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review
from tariffpeg.sample.calibration import (
    LEAST_REVIEWS,
    TOLERANCE,
    Calibration,
    compare,
    look_back,
    median_points,
    window,
)

DIGEST = "sha256:" + "a" * 64
AT = StayMonth(2026, 6)
BODY = "The rooms were clean and the harbour walk starts right outside the door."


def review(number: str, points: int, month: StayMonth, channel: str = "seaboard") -> Review:
    return Review(
        channel=channel,
        channel_review_id=number,
        licence_serial=4021,
        stay=month,
        unit_points=points,
        raw_score="8.0",
        body=f"{BODY} Filed as {number}.",
        capture_digest=DIGEST,
        profile_key=f"{channel}/v1",
    )


def run(
    points: int, count: int, month: StayMonth, start: int = 0, channel: str = "seaboard"
) -> list[Review]:
    return [review(str(start + n), points, month, channel) for n in range(count)]


def test_the_middle_score_of_an_odd_run_is_the_middle_one() -> None:
    held = [review("1", 10, AT), review("2", 50, AT), review("3", 90, AT)]
    assert median_points(held) == 50


def test_the_middle_score_of_an_even_run_is_between_the_two() -> None:
    held = [review("1", 10, AT), review("2", 50, AT)]
    assert median_points(held) == 30


def test_the_middle_of_an_empty_set_is_refused() -> None:
    with pytest.raises(Invalid, match="no middle"):
        median_points([])


def test_a_window_counts_only_the_channel_and_the_months_it_covers() -> None:
    held = [
        *run(80, 3, StayMonth(2026, 5)),
        *run(20, 3, StayMonth(2025, 1), start=100),
        *run(40, 3, StayMonth(2026, 5), start=200, channel="quayside"),
    ]
    found = window("seaboard", held, StayMonth(2026, 1), AT)
    assert found.count == 3
    assert found.median_points == 80


def test_a_window_with_nothing_in_it_counts_nothing() -> None:
    found = window("seaboard", [], StayMonth(2026, 1), AT)
    assert found.count == 0
    assert found.median_points == 0
    assert found.thin


def test_a_window_that_ends_before_it_starts_is_refused() -> None:
    with pytest.raises(Invalid, match="ends after it starts"):
        window("seaboard", [], AT, StayMonth(2025, 1))


def test_a_window_below_the_floor_is_thin() -> None:
    held = run(80, LEAST_REVIEWS - 1, StayMonth(2026, 5))
    assert window("seaboard", held, StayMonth(2026, 1), AT).thin
    enough = run(80, LEAST_REVIEWS, StayMonth(2026, 5))
    assert not window("seaboard", enough, StayMonth(2026, 1), AT).thin


def test_two_windows_that_agree_say_the_table_holds() -> None:
    earlier = window(
        "seaboard", run(74, 30, StayMonth(2025, 5)), StayMonth(2025, 1), StayMonth(2025, 12)
    )
    later = window("seaboard", run(76, 30, StayMonth(2026, 5), start=99), StayMonth(2026, 1), AT)
    found = compare(earlier, later)
    assert found.verdict is Calibration.HOLDS
    assert found.shift == 2
    assert "the anchor table holds" in found.line()


def test_a_median_that_has_moved_too_far_doubts_the_table() -> None:
    earlier = window(
        "seaboard", run(50, 30, StayMonth(2025, 5)), StayMonth(2025, 1), StayMonth(2025, 12)
    )
    later = window("seaboard", run(80, 30, StayMonth(2026, 5), start=99), StayMonth(2026, 1), AT)
    found = compare(earlier, later)
    assert found.verdict is Calibration.DRIFTED
    assert found.shift == 30
    assert "wants agreeing again" in found.line()


def test_a_median_that_moved_down_is_reported_the_same_way() -> None:
    earlier = window(
        "seaboard", run(80, 30, StayMonth(2025, 5)), StayMonth(2025, 1), StayMonth(2025, 12)
    )
    later = window("seaboard", run(50, 30, StayMonth(2026, 5), start=99), StayMonth(2026, 1), AT)
    found = compare(earlier, later)
    assert found.shift == -30
    assert "-30 points" in found.line()


def test_a_thin_window_says_so_rather_than_calling_it_either_way() -> None:
    earlier = window(
        "seaboard", run(50, 3, StayMonth(2025, 5)), StayMonth(2025, 1), StayMonth(2025, 12)
    )
    later = window("seaboard", run(90, 30, StayMonth(2026, 5), start=99), StayMonth(2026, 1), AT)
    found = compare(earlier, later)
    assert found.verdict is Calibration.THIN
    assert "too few reviews to say" in found.line()


def test_the_tolerance_can_be_widened_when_the_unit_says_so() -> None:
    earlier = window(
        "seaboard", run(50, 30, StayMonth(2025, 5)), StayMonth(2025, 1), StayMonth(2025, 12)
    )
    later = window("seaboard", run(60, 30, StayMonth(2026, 5), start=99), StayMonth(2026, 1), AT)
    assert compare(earlier, later).verdict is Calibration.DRIFTED
    assert compare(earlier, later, tolerance=20).verdict is Calibration.HOLDS


def test_a_negative_tolerance_is_refused() -> None:
    earlier = window("seaboard", [], StayMonth(2025, 1), StayMonth(2025, 12))
    with pytest.raises(Invalid, match="not negative"):
        compare(earlier, earlier, tolerance=-1)


def test_two_windows_of_different_channels_do_not_compare() -> None:
    one = window("seaboard", [], StayMonth(2025, 1), StayMonth(2025, 12))
    other = window("quayside", [], StayMonth(2026, 1), AT)
    with pytest.raises(Invalid, match="do not compare"):
        compare(one, other)


def test_looking_back_sets_the_last_year_against_the_one_before_it() -> None:
    held = [
        *run(50, 30, StayMonth(2025, 5)),
        *run(90, 30, StayMonth(2026, 5), start=99),
    ]
    found = look_back("seaboard", held, AT)
    assert found.verdict is Calibration.DRIFTED
    assert found.earlier.count == 30
    assert found.later.count == 30


def test_looking_back_over_no_months_is_refused() -> None:
    with pytest.raises(Invalid, match="a month or more"):
        look_back("seaboard", [], AT, months=0)


def test_the_published_tolerance_is_a_handful_of_points() -> None:
    assert 0 < TOLERANCE < 20
