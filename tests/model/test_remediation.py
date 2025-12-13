"""The date that matters is the month the work finished, not the date on the notice."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.period import StayMonth
from tariffpeg.model.remediation import BACKDATE_MONTHS, Remediation


def notice(**over: object) -> Remediation:
    base: dict[str, object] = {
        "licence_serial": 4021,
        "claim_key": "lift",
        "reference": "RN-2026-0118",
        "filed_on": dt.date(2026, 3, 4),
        "effective_from": StayMonth(2026, 1),
    }
    base.update(over)
    return Remediation(**base)  # type: ignore[arg-type]


def test_the_key_names_the_licence_the_particular_and_the_notice() -> None:
    assert notice().key == "4021:lift:RN-2026-0118"


def test_a_notice_about_a_particular_nobody_registers_is_refused() -> None:
    with pytest.raises(Invalid, match="no such particular"):
        notice(claim_key="sauna")


def test_a_notice_needs_the_number_it_was_filed_under() -> None:
    with pytest.raises(Invalid, match="the number it was filed under"):
        notice(reference="   ")


def test_the_work_cannot_have_finished_after_the_notice_was_filed() -> None:
    with pytest.raises(Invalid, match="after the notice was filed"):
        notice(effective_from=StayMonth(2026, 4))


def test_the_work_may_have_finished_in_the_month_the_notice_was_filed() -> None:
    assert notice(effective_from=StayMonth(2026, 3)).effective_from == StayMonth(2026, 3)


def test_a_notice_cannot_reach_back_indefinitely() -> None:
    filed = dt.date(2026, 3, 4)
    edge = StayMonth(2026, 3).minus(BACKDATE_MONTHS)
    assert notice(filed_on=filed, effective_from=edge).effective_from == edge
    with pytest.raises(Invalid, match="reach back more than"):
        notice(filed_on=filed, effective_from=edge.minus(1))


def test_a_stay_after_the_work_is_covered_and_one_before_it_is_not() -> None:
    filed = notice()
    assert filed.covers(StayMonth(2026, 1))
    assert filed.covers(StayMonth(2026, 6))
    assert not filed.covers(StayMonth(2025, 12))


def test_a_notice_starts_out_not_yet_accepted() -> None:
    assert not notice().accepted
    assert notice().note == ""


def test_accepting_a_notice_returns_a_copy() -> None:
    accepted = notice().accept("the lift certificate was produced")
    assert accepted.accepted
    assert "certificate" in accepted.note
    assert not notice().accepted


def test_accepting_without_a_note_keeps_whatever_note_was_there() -> None:
    assert notice(note="seen by the inspector").accept().note == "seen by the inspector"


def test_refusing_a_notice_records_why() -> None:
    refused = notice().refuse("no certificate was produced")
    assert not refused.accepted
    assert "no certificate" in refused.note


def test_refusing_without_a_reason_is_refused() -> None:
    with pytest.raises(Invalid, match="says why it was refused"):
        notice().refuse("  ")


def test_a_negative_serial_is_refused() -> None:
    with pytest.raises(Invalid, match="not negative"):
        notice(licence_serial=-1)
