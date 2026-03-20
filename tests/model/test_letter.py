"""An operator who says they were never told is answered with this."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Conflict, Invalid
from tariffpeg.model.letter import REPLY_DAYS, Letter, Sent

DIGEST = "sha256:" + "c" * 64
SENT = dt.date(2026, 6, 1)


def letter(**over: object) -> Letter:
    base: dict[str, object] = {
        "reference": "DE-2026-0044",
        "operator_ref": "pellow-and-daughter",
        "licence_serial": 4021,
        "kind": Sent.DESK_ENQUIRY,
        "sent_on": SENT,
        "subject": "The passenger lift at The Anchor Rooms",
        "body_digest": DIGEST,
    }
    base.update(over)
    return Letter(**base)  # type: ignore[arg-type]


def test_a_letter_carries_the_number_it_went_under() -> None:
    with pytest.raises(Invalid, match="the number it went under"):
        letter(reference="  ")
    assert letter().key == "DE-2026-0044"


def test_a_letter_goes_to_an_operator_on_the_register() -> None:
    with pytest.raises(Invalid, match="goes to an operator"):
        letter(operator_ref="Pellow and Daughter")


def test_a_letter_says_what_it_is_about() -> None:
    with pytest.raises(Invalid, match="says what it is about"):
        letter(subject="   ")


def test_a_letter_carries_the_digest_of_itself() -> None:
    with pytest.raises(Invalid, match="digest of itself"):
        letter(body_digest="deadbeef")


def test_a_negative_serial_is_refused() -> None:
    with pytest.raises(Invalid, match="not negative"):
        letter(licence_serial=-1)


def test_a_reply_dated_before_the_letter_is_refused() -> None:
    with pytest.raises(Conflict, match="before the letter it answers"):
        letter(replied_on=SENT - dt.timedelta(days=1))


def test_a_letter_starts_out_with_no_reply_against_it() -> None:
    assert not letter().answered
    assert letter().replied_on is None


def test_recording_a_reply_returns_a_copy() -> None:
    answered = letter().with_reply(dt.date(2026, 6, 8))
    assert answered.answered
    assert answered.replied_on == dt.date(2026, 6, 8)
    assert not letter().answered


def test_each_kind_of_letter_gives_its_own_number_of_days() -> None:
    assert set(REPLY_DAYS) == set(Sent)
    assert REPLY_DAYS[Sent.NOTICE_OF_INSPECTION] < REPLY_DAYS[Sent.DESK_ENQUIRY]


def test_the_reply_clock_runs_in_working_days() -> None:
    held = letter()
    assert held.due_on() == dt.date(2026, 6, 19)


def test_a_holiday_pushes_the_reply_day_out() -> None:
    held = letter()
    holidays = frozenset({dt.date(2026, 6, 8)})
    assert held.due_on(holidays) > held.due_on()


def test_a_reply_that_has_not_come_is_late_after_the_day_it_was_due() -> None:
    held = letter()
    assert not held.overdue_on(held.due_on())
    assert held.overdue_on(held.due_on() + dt.timedelta(days=1))


def test_a_letter_that_was_answered_is_never_late() -> None:
    held = letter().with_reply(dt.date(2026, 6, 8))
    assert not held.overdue_on(dt.date(2027, 1, 1))


def test_a_reply_that_came_after_the_day_it_was_due_is_marked_late() -> None:
    on_time = letter().with_reply(dt.date(2026, 6, 8))
    late = letter().with_reply(dt.date(2026, 7, 1))
    assert not on_time.answered_late()
    assert late.answered_late()


def test_a_letter_nobody_answered_is_not_marked_as_answered_late() -> None:
    assert not letter().answered_late()
