"""The overnight job needs one answer, and it has to tell bad from behind."""

from __future__ import annotations

from tariffpeg.report.health import (
    CLEAR,
    FAULT,
    WARNING,
    Health,
    Reading,
    clear,
    fault,
    warning,
    worst_of,
)


def test_a_fault_and_a_warning_are_both_worth_acting_on() -> None:
    assert fault("store", "it does not verify").bad
    assert warning("letters", "two are late").bad
    assert not clear("sample").bad


def test_a_reading_with_nothing_to_say_still_prints_a_row() -> None:
    assert clear("sample").row()["detail"] == "nothing to say"


def test_a_reading_prints_what_it_found() -> None:
    row = warning("letters", "two are late").row()
    assert row["check"] == "letters"
    assert row["state"] == WARNING
    assert row["detail"] == "two are late"


def test_a_reading_with_nothing_wrong_anywhere_is_sound() -> None:
    found = Health((clear("store"), clear("letters")))
    assert found.sound
    assert found.exit_code() == 0
    assert "nothing to act on" in found.summary()


def test_a_unit_that_is_behind_exits_one() -> None:
    found = Health((clear("store"), warning("letters", "two are late")))
    assert not found.sound
    assert found.faults() == ()
    assert found.exit_code() == 1
    assert "1 faults" not in found.summary()


def test_a_store_that_cannot_be_relied_on_exits_two() -> None:
    found = Health((fault("store", "it does not verify"), warning("letters", "late")))
    assert found.exit_code() == 2
    assert [reading.name for reading in found.faults()] == ["store"]
    assert [reading.name for reading in found.warnings()] == ["letters"]
    assert "1 faults and 1 warnings" in found.summary()


def test_a_reading_of_nothing_at_all_is_sound() -> None:
    assert Health().sound
    assert Health().rows() == []
    assert Health().exit_code() == 0


def test_the_worst_of_a_set_of_readings_is_the_one_that_matters() -> None:
    assert worst_of([clear("a"), warning("b", "x"), fault("c", "y")]) == FAULT
    assert worst_of([clear("a"), warning("b", "x")]) == WARNING
    assert worst_of([clear("a")]) == CLEAR
    assert worst_of([]) == CLEAR


def test_a_reading_built_by_hand_carries_the_state_it_was_given() -> None:
    assert Reading("store", FAULT, "broken").state == FAULT
