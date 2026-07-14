"""A run that fills one diary and leaves another empty is a run worth doing again."""

from __future__ import annotations

import datetime as dt

from tariffpeg.report.workload import Load, Week, spread, weeks_between
from tariffpeg.triage.disposition import Disposition
from tariffpeg.triage.schedule import Booking, Diary

MONDAY = dt.date(2025, 9, 1)
DIARIES = (Diary("Ivell", 2), Diary("Trethowan", 2))


def booking(serial: int, inspector: str, day: dt.date) -> Booking:
    return Booking(serial, inspector, day, Disposition.REINSPECTION)


def test_a_week_that_is_not_full_says_how_much_room_is_left() -> None:
    week = Week(2025, 36, 1, 4)
    assert week.spare == 3
    assert not week.full
    assert week.label() == "2025w36"


def test_a_week_booked_past_its_capacity_has_no_room_left() -> None:
    week = Week(2025, 36, 5, 4)
    assert week.spare == 0
    assert week.full


def test_the_span_covers_every_week_from_the_first_visit_to_the_last() -> None:
    found = weeks_between(MONDAY, MONDAY + dt.timedelta(days=21))
    assert len(found) == 4
    assert found[0] == (2025, 36)


def test_a_span_inside_one_week_is_that_week_alone() -> None:
    assert weeks_between(MONDAY, MONDAY + dt.timedelta(days=2)) == ((2025, 36),)


def test_an_inspector_with_nothing_booked_is_idle() -> None:
    assert Load("Ivell", (Week(2025, 36, 0, 2),)).idle


def test_the_busiest_week_is_the_one_with_the_most_in_it() -> None:
    load = Load("Ivell", (Week(2025, 36, 1, 2), Week(2025, 37, 2, 2)))
    assert load.busiest == 2
    assert load.visits == 3
    assert load.spare == 1


def test_every_inspector_appears_even_the_ones_given_nothing() -> None:
    found = spread([booking(1, "Ivell", MONDAY)], DIARIES)
    assert [load.inspector for load in found.loads] == ["Ivell", "Trethowan"]
    assert found.idle() == ("Trethowan",)


def test_the_heaviest_diary_comes_first() -> None:
    bookings = [
        booking(1, "Trethowan", MONDAY),
        booking(2, "Ivell", MONDAY),
        booking(3, "Ivell", MONDAY + dt.timedelta(days=1)),
    ]
    found = spread(bookings, DIARIES)
    assert [load.inspector for load in found.loads] == ["Ivell", "Trethowan"]


def test_spare_capacity_is_counted_over_the_whole_span_not_the_weeks_worked() -> None:
    bookings = [booking(1, "Ivell", MONDAY), booking(2, "Ivell", MONDAY + dt.timedelta(days=14))]
    found = spread(bookings, DIARIES)
    idle = [load for load in found.loads if load.inspector == "Trethowan"][0]
    assert len(idle.weeks) == 3
    assert idle.spare == 6


def test_a_full_week_beside_an_empty_diary_reads_as_lopsided() -> None:
    bookings = [
        booking(1, "Ivell", MONDAY),
        booking(2, "Ivell", MONDAY + dt.timedelta(days=1)),
    ]
    found = spread(bookings, DIARIES)
    assert found.lopsided()
    assert [load.full_weeks for load in found.loads][0] == ("2025w36",)


def test_a_run_that_left_nobody_idle_does_not_read_as_lopsided() -> None:
    bookings = [
        booking(1, "Ivell", MONDAY),
        booking(2, "Ivell", MONDAY + dt.timedelta(days=1)),
        booking(3, "Trethowan", MONDAY),
    ]
    assert not spread(bookings, DIARIES).lopsided()


def test_a_run_with_room_everywhere_does_not_read_as_lopsided() -> None:
    assert not spread([booking(1, "Ivell", MONDAY)], DIARIES).lopsided()


def test_the_visits_that_missed_their_target_are_counted_per_inspector() -> None:
    bookings = [booking(1, "Ivell", MONDAY), booking(2, "Trethowan", MONDAY)]
    found = spread(bookings, DIARIES, late=[1])
    assert {load.inspector: load.late for load in found.loads} == {"Ivell": 1, "Trethowan": 0}


def test_a_row_carries_the_first_and_last_day_that_inspector_travels() -> None:
    bookings = [booking(1, "Ivell", MONDAY), booking(2, "Ivell", MONDAY + dt.timedelta(days=8))]
    rows = spread(bookings, DIARIES).rows()
    assert rows[0]["first"] == MONDAY.isoformat()
    assert rows[0]["last"] == (MONDAY + dt.timedelta(days=8)).isoformat()
    assert rows[1]["first"] == "none"


def test_a_run_that_booked_nothing_has_no_span_at_all() -> None:
    found = spread([], DIARIES)
    assert found.span == ()
    assert found.idle() == ("Ivell", "Trethowan")
    assert not found.lopsided()
