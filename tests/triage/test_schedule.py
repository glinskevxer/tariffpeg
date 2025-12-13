"""There is nothing to inspect at a premises that is shut."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.licence import Licence
from tariffpeg.triage.disposition import Disposition
from tariffpeg.triage.schedule import (
    NOTICE_DAYS,
    Booking,
    Diary,
    Refusal,
    Scheduler,
    add_working_days,
    diaries_by_name,
    is_working_day,
)

DECIDED = dt.date(2025, 6, 2)


def licence(closed: frozenset[int] = frozenset()) -> Licence:
    return Licence(
        serial=4021,
        trading_name="The Anchor Rooms",
        operator_name="Pellow and Daughter",
        locality="Porthgwarra",
        period_start=dt.date(2025, 1, 1),
        period_end=dt.date(2026, 12, 31),
        particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18},
        closed_months=closed,
    )


def test_a_weekend_is_not_a_working_day() -> None:
    assert is_working_day(dt.date(2025, 6, 2))
    assert not is_working_day(dt.date(2025, 6, 7))
    assert not is_working_day(dt.date(2025, 6, 8))


def test_a_holiday_is_not_a_working_day() -> None:
    holidays = frozenset({dt.date(2025, 6, 2)})
    assert not is_working_day(dt.date(2025, 6, 2), holidays)


def test_working_days_are_counted_over_the_weekend() -> None:
    assert add_working_days(dt.date(2025, 6, 5), 1) == dt.date(2025, 6, 6)
    assert add_working_days(dt.date(2025, 6, 5), 2) == dt.date(2025, 6, 9)
    assert add_working_days(dt.date(2025, 6, 5), 0) == dt.date(2025, 6, 5)


def test_counting_working_days_backwards_is_refused() -> None:
    with pytest.raises(Invalid, match="counted forwards"):
        add_working_days(DECIDED, -1)


def test_a_visit_lands_after_the_notice_period() -> None:
    booking = Scheduler([Diary("Trewin")]).book(licence(), Disposition.REINSPECTION, DECIDED)
    assert isinstance(booking, Booking)
    assert booking.day >= add_working_days(DECIDED, NOTICE_DAYS)
    assert booking.inspector == "Trewin"


def test_a_disposition_that_sends_nobody_out_books_nothing() -> None:
    for disposition in (Disposition.NO_ACTION, Disposition.DESK_ENQUIRY):
        found = Scheduler([Diary("Trewin")]).book(licence(), disposition, DECIDED)
        assert isinstance(found, Refusal)
        assert "does not send anybody out" in found.reason


def test_a_visit_never_lands_on_a_weekend() -> None:
    scheduler = Scheduler([Diary("Trewin")])
    booking = scheduler.book(licence(), Disposition.URGENT, dt.date(2025, 6, 4))
    assert isinstance(booking, Booking)
    assert booking.day.weekday() < 5


def test_a_visit_never_lands_on_a_holiday() -> None:
    holidays = frozenset({dt.date(2025, 6, 4), dt.date(2025, 6, 5), dt.date(2025, 6, 6)})
    scheduler = Scheduler([Diary("Trewin")], holidays)
    booking = scheduler.book(licence(), Disposition.URGENT, DECIDED)
    assert isinstance(booking, Booking)
    assert booking.day not in holidays


def test_an_urgent_visit_waits_for_a_premises_that_is_shut() -> None:
    winter = licence(closed=frozenset({6, 7, 8}))
    booking = Scheduler([Diary("Trewin")]).book(winter, Disposition.URGENT, DECIDED)
    assert isinstance(booking, Booking)
    assert booking.day.month == 9


def test_a_visit_outside_the_licence_period_is_refused() -> None:
    short = Licence(
        serial=4021,
        trading_name="The Anchor Rooms",
        operator_name="Pellow and Daughter",
        locality="Porthgwarra",
        period_start=dt.date(2025, 1, 1),
        period_end=dt.date(2025, 6, 1),
        particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18},
    )
    found = Scheduler([Diary("Trewin")]).book(short, Disposition.URGENT, DECIDED)
    assert isinstance(found, Refusal)
    assert "anybody free" in found.reason


def test_an_inspector_who_is_away_does_not_get_the_visit() -> None:
    away = frozenset({dt.date(2025, 6, 4), dt.date(2025, 6, 5), dt.date(2025, 6, 6)})
    scheduler = Scheduler([Diary("Trewin", away=away), Diary("Angove")])
    booking = scheduler.book(licence(), Disposition.URGENT, DECIDED)
    assert isinstance(booking, Booking)
    assert booking.inspector == "Angove"


def test_a_full_week_pushes_the_visit_into_the_next_one() -> None:
    scheduler = Scheduler([Diary("Trewin", weekly_capacity=1)])
    first = scheduler.book(licence(), Disposition.URGENT, DECIDED)
    second = scheduler.book(licence(), Disposition.URGENT, DECIDED)
    assert isinstance(first, Booking)
    assert isinstance(second, Booking)
    assert second.week != first.week


def test_a_second_inspector_takes_the_overflow_inside_the_same_week() -> None:
    scheduler = Scheduler([Diary("Trewin", weekly_capacity=1), Diary("Angove", weekly_capacity=1)])
    first = scheduler.book(licence(), Disposition.URGENT, DECIDED)
    second = scheduler.book(licence(), Disposition.URGENT, DECIDED)
    assert isinstance(first, Booking)
    assert isinstance(second, Booking)
    assert second.week == first.week
    assert {first.inspector, second.inspector} == {"Trewin", "Angove"}


def test_the_load_counts_only_the_week_that_is_asked_about() -> None:
    scheduler = Scheduler([Diary("Trewin")])
    booking = scheduler.book(licence(), Disposition.URGENT, DECIDED)
    assert isinstance(booking, Booking)
    assert scheduler.load("Trewin", booking.week) == 1
    assert scheduler.load("Trewin", (2030, 1)) == 0
    assert scheduler.load("Nobody", booking.week) == 0


def test_an_urgent_visit_that_makes_its_target_is_not_overdue() -> None:
    scheduler = Scheduler([Diary("Trewin")])
    booking = scheduler.book(licence(), Disposition.URGENT, DECIDED)
    assert isinstance(booking, Booking)
    assert not scheduler.overdue(booking, DECIDED)


def test_a_visit_pushed_past_its_target_is_reported_as_late() -> None:
    winter = licence(closed=frozenset({6, 7, 8, 9, 10}))
    scheduler = Scheduler([Diary("Trewin")])
    booking = scheduler.book(winter, Disposition.URGENT, DECIDED)
    assert isinstance(booking, Booking)
    assert scheduler.overdue(booking, DECIDED)
    assert any("late" in line for line in scheduler.report(DECIDED))


def test_the_report_lists_the_bookings_by_day() -> None:
    scheduler = Scheduler([Diary("Trewin"), Diary("Angove")])
    scheduler.book(licence(), Disposition.URGENT, DECIDED)
    scheduler.book(licence(), Disposition.REINSPECTION, DECIDED)
    lines = scheduler.report(DECIDED)
    assert len(lines) == 2
    assert all(line.startswith("4021 to ") for line in lines)


def test_a_scheduler_with_nobody_in_it_is_refused() -> None:
    with pytest.raises(Invalid, match="nobody to send"):
        Scheduler([])


def test_a_diary_needs_a_name_and_room_for_one_visit() -> None:
    with pytest.raises(Invalid, match="a name in the diary"):
        Diary("  ")
    with pytest.raises(Invalid, match="one visit or more"):
        Diary("Trewin", weekly_capacity=0)


def test_a_diary_knows_the_days_it_is_away() -> None:
    diary = Diary("Trewin", away=frozenset({dt.date(2025, 6, 4)}))
    assert not diary.free_on(dt.date(2025, 6, 4))
    assert diary.free_on(dt.date(2025, 6, 5))


def test_the_diaries_can_be_looked_up_by_name() -> None:
    found = diaries_by_name([Diary("Trewin"), Diary("Angove")])
    assert sorted(found) == ["Angove", "Trewin"]
