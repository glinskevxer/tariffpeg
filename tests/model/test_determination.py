"""A minute records what the unit acted on, not what it would decide today."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.determination import (
    ESCALATED,
    HELD,
    STEPPED_BACK,
    Determination,
    movement,
    unexplained,
)
from tariffpeg.model.outcome import Disposition
from tariffpeg.model.period import StayMonth

AT = StayMonth(2025, 9)
MINUTED = dt.datetime(2025, 10, 2, 9, 30, tzinfo=dt.UTC)


def minute(**over: object) -> Determination:
    base: dict[str, object] = {
        "licence_serial": 4021,
        "decided_at": AT,
        "disposition": Disposition.DESK_ENQUIRY,
        "score": 4.5,
        "access_score": 0.0,
        "capped": False,
        "pack_version": 2,
        "minuted_at": MINUTED,
        "officer": "R Bosustow",
    }
    base.update(over)
    return Determination(**base)  # type: ignore[arg-type]


def test_a_minute_is_held_under_the_licence_and_the_month_it_decided() -> None:
    assert minute().key == (4021, 2025, 9)


def test_a_minute_that_sends_nobody_out_says_so() -> None:
    assert not minute().sent_somebody_out
    assert minute(disposition=Disposition.URGENT).sent_somebody_out


def test_the_line_names_the_pack_and_the_officer() -> None:
    line = minute().line()
    assert "under pack 2" in line
    assert "R Bosustow" in line
    assert "capped" not in line


def test_a_minute_capped_by_the_sample_says_that_on_its_line() -> None:
    assert "capped by an incomplete sample" in minute(capped=True).line()


def test_a_minute_with_no_officer_on_it_is_refused() -> None:
    with pytest.raises(Invalid, match="the name of who took it"):
        minute(officer="  ")


def test_a_minute_stamped_without_an_offset_is_refused() -> None:
    with pytest.raises(ValueError, match="minuted_at has no timezone"):
        minute(minuted_at=dt.datetime(2025, 10, 2, 9, 30))


def test_a_minute_under_no_pack_at_all_is_refused() -> None:
    with pytest.raises(Invalid, match="rule pack versions start at one"):
        minute(pack_version=0)


def test_a_minute_with_a_serial_below_one_is_refused() -> None:
    with pytest.raises(Invalid, match="a serial counts from one"):
        minute(licence_serial=0)


def test_a_negative_score_is_refused() -> None:
    with pytest.raises(Invalid, match="does not go below zero"):
        minute(score=-1.0)


def test_two_minutes_at_the_same_disposition_held() -> None:
    later = minute(decided_at=StayMonth(2025, 10))
    assert movement(minute(), later) == HELD


def test_a_minute_further_up_the_order_escalated() -> None:
    later = minute(decided_at=StayMonth(2025, 10), disposition=Disposition.URGENT)
    assert movement(minute(), later) == ESCALATED


def test_a_minute_back_down_the_order_stepped_back() -> None:
    later = minute(decided_at=StayMonth(2025, 10), disposition=Disposition.NO_ACTION)
    assert movement(minute(), later) == STEPPED_BACK


def test_a_score_that_climbed_without_crossing_a_band_still_held() -> None:
    later = minute(decided_at=StayMonth(2025, 10), score=6.9)
    assert movement(minute(), later) == HELD


def test_comparing_minutes_from_two_different_licences_is_refused() -> None:
    with pytest.raises(Invalid, match="not the same case"):
        movement(minute(), minute(licence_serial=4022))


def test_a_step_back_under_the_same_pack_wants_looking_at() -> None:
    later = minute(decided_at=StayMonth(2025, 10), disposition=Disposition.NO_ACTION)
    assert unexplained(minute(), later)


def test_a_step_back_after_a_new_pack_is_ordinary() -> None:
    before = minute(pack_version=1)
    later = minute(decided_at=StayMonth(2025, 10), disposition=Disposition.NO_ACTION)
    assert not unexplained(before, later)


def test_an_escalation_is_never_unexplained() -> None:
    later = minute(decided_at=StayMonth(2025, 10), disposition=Disposition.URGENT)
    assert not unexplained(minute(), later)
