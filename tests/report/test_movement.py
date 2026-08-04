"""A licence that escalated since it was minuted is a letter nobody has sent."""

from __future__ import annotations

import datetime as dt

from tariffpeg.model.determination import ESCALATED, HELD, STEPPED_BACK, Determination
from tariffpeg.model.outcome import Disposition
from tariffpeg.model.period import StayMonth
from tariffpeg.report.movement import UNMINUTED, Movement, Reconciliation, reconcile
from tariffpeg.triage.disposition import Decision

AT = StayMonth(2025, 9)
MINUTED = dt.datetime(2025, 10, 2, 9, 30, tzinfo=dt.UTC)


def minute(
    serial: int = 4021,
    disposition: Disposition = Disposition.DESK_ENQUIRY,
    pack_version: int = 2,
) -> Determination:
    return Determination(
        licence_serial=serial,
        decided_at=AT,
        disposition=disposition,
        score=4.5,
        access_score=0.0,
        capped=False,
        pack_version=pack_version,
        minuted_at=MINUTED,
        officer="R Bosustow",
    )


def decision(serial: int = 4021, disposition: Disposition = Disposition.DESK_ENQUIRY) -> Decision:
    return Decision(serial, disposition, 4.5, 0.0, (), ())


def test_a_licence_reading_the_same_way_it_was_minuted_held() -> None:
    item = Movement(4021, minute(), Disposition.DESK_ENQUIRY, 2)
    assert item.moved == HELD
    assert not item.wants_a_letter
    assert not item.unexplained


def test_a_licence_that_reads_worse_now_wants_a_letter() -> None:
    item = Movement(4021, minute(), Disposition.URGENT, 2)
    assert item.moved == ESCALATED
    assert item.wants_a_letter
    assert item.unexplained


def test_a_licence_that_reads_better_now_does_not_want_a_letter() -> None:
    item = Movement(4021, minute(), Disposition.NO_ACTION, 2)
    assert item.moved == STEPPED_BACK
    assert not item.wants_a_letter


def test_a_move_under_a_new_pack_explains_itself() -> None:
    item = Movement(4021, minute(pack_version=1), Disposition.URGENT, 2)
    assert not item.same_pack
    assert not item.unexplained


def test_a_licence_the_ledger_has_never_held_says_so() -> None:
    item = Movement(4021, None, Disposition.URGENT, 2)
    assert not item.known
    assert item.moved == UNMINUTED
    assert not item.wants_a_letter
    assert item.row()["minuted"] == "never"
    assert item.row()["then"] == ""


def test_the_row_names_both_readings() -> None:
    row = Movement(4021, minute(), Disposition.URGENT, 2).row()
    assert row["then"] == str(Disposition.DESK_ENQUIRY)
    assert row["now"] == str(Disposition.URGENT)
    assert row["pack"] is True


def test_the_licences_come_back_in_serial_order() -> None:
    found = reconcile({}, [decision(4022), decision(4021)], 2)
    assert [item.licence_serial for item in found.movements] == [4021, 4022]


def test_a_minuted_licence_with_no_live_decision_is_left_out() -> None:
    found = reconcile({4021: minute(), 4099: minute(4099)}, [decision(4021)], 2)
    assert [item.licence_serial for item in found.movements] == [4021]


def test_a_register_that_has_not_moved_is_settled() -> None:
    found = reconcile({4021: minute()}, [decision()], 2)
    assert found.settled()
    assert found.moved() == ()
    assert found.wanting_a_letter() == ()


def test_a_register_that_has_moved_names_what_moved() -> None:
    found = reconcile({4021: minute()}, [decision(disposition=Disposition.URGENT)], 2)
    assert not found.settled()
    assert [item.licence_serial for item in found.moved()] == [4021]
    assert found.wanting_a_letter() == (4021,)


def test_the_licences_nobody_has_minuted_are_counted_on_their_own() -> None:
    found = reconcile({4021: minute()}, [decision(), decision(4022)], 2)
    assert found.unminuted() == (4022,)
    assert found.settled()


def test_a_reconciliation_of_an_empty_register_holds_nothing() -> None:
    assert Reconciliation().rows() == []
    assert Reconciliation().settled()
    assert Reconciliation().unminuted() == ()
