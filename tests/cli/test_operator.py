"""A letter goes to the person who holds the licence, not the name on the door."""

from __future__ import annotations

from tests.cli.conftest import Run
from tests.cli.test_channel import ADD_LICENCE, REF

ADD_OPERATOR = (
    "operator",
    "add",
    "pellow-and-daughter",
    "--name",
    "Pellow and Daughter",
    "--contact",
    "R Pellow",
    "--email",
    "office@pellow.example",
    "--address",
    "1 Quay Street, Porthgwarra",
    "--registered",
    "2019-04-01",
)


def test_an_operator_is_registered_and_reads_back(migrated: Run) -> None:
    result = migrated(*ADD_OPERATOR)
    assert result.exit_code == 0
    listed = migrated("operator", "list")
    assert "Pellow and Daughter" in listed.output
    assert "R Pellow" in listed.output


def test_an_address_a_letter_cannot_go_to_is_refused(migrated: Run) -> None:
    result = migrated(*ADD_OPERATOR[:-2], "--email", "not an address")
    assert result.exit_code != 0


def test_the_same_operator_twice_is_refused(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    assert migrated(*ADD_OPERATOR).exit_code == 4


def test_an_empty_register_says_so(migrated: Run) -> None:
    assert "nobody is on the operator register" in migrated("operator", "list").output


def test_an_operator_holds_a_licence_once_it_is_tied_to_them(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    migrated(*ADD_LICENCE)
    result = migrated("operator", "hold", REF, "pellow-and-daughter")
    assert result.exit_code == 0
    shown = migrated("operator", "show", "pellow-and-daughter")
    assert REF in shown.output
    assert "The Anchor Rooms" in shown.output


def test_an_operator_holding_nothing_says_so(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    assert "they hold no licences" in migrated("operator", "show", "pellow-and-daughter").output


def test_the_letter_line_names_the_person_and_the_operator(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    shown = migrated("operator", "show", "pellow-and-daughter")
    assert "write to R Pellow, Pellow and Daughter" in shown.output
    assert "on the register since 2019-04-01" in shown.output


def test_the_person_to_write_to_can_be_changed(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    result = migrated(
        "operator",
        "contact",
        "pellow-and-daughter",
        "--contact",
        "J Pellow",
        "--email",
        "jp@pellow.example",
    )
    assert result.exit_code == 0
    assert "J Pellow" in migrated("operator", "show", "pellow-and-daughter").output


def test_a_contact_change_with_an_address_that_will_not_do_is_refused(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    result = migrated(
        "operator",
        "contact",
        "pellow-and-daughter",
        "--contact",
        "J Pellow",
        "--email",
        "nowhere",
    )
    assert result.exit_code == 2


def test_the_register_can_be_narrowed_to_those_holding_several(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    migrated(*ADD_LICENCE)
    migrated("operator", "hold", REF, "pellow-and-daughter")
    assert "pellow-and-daughter" in migrated("operator", "list", "--holding", "1").output
    assert (
        "nobody is on the operator register"
        in migrated("operator", "list", "--holding", "2").output
    )


def test_tying_a_licence_to_an_operator_nobody_registered_is_refused(migrated: Run) -> None:
    migrated(*ADD_LICENCE)
    assert migrated("operator", "hold", REF, "nowhere").exit_code == 3


def test_an_operator_can_be_taken_off_the_register(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    assert migrated("operator", "remove", "pellow-and-daughter", "--yes").exit_code == 0
    assert "nobody is on" in migrated("operator", "list").output


def test_an_operator_still_holding_a_licence_cannot_be_taken_off(migrated: Run) -> None:
    migrated(*ADD_OPERATOR)
    migrated(*ADD_LICENCE)
    migrated("operator", "hold", REF, "pellow-and-daughter")
    result = migrated("operator", "remove", "pellow-and-daughter", "--yes")
    assert result.exit_code == 4


def test_showing_an_operator_nobody_registered_is_refused(migrated: Run) -> None:
    assert migrated("operator", "show", "nowhere").exit_code == 3
