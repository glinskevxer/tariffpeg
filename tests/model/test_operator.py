"""A pattern across three premises is a different conversation from one at one."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.operator import Operator


def operator(**over: object) -> Operator:
    base: dict[str, object] = {
        "ref": "pellow-and-daughter",
        "name": "Pellow and Daughter",
        "contact_name": "R Pellow",
        "email": "office@pellow.example",
        "address": "1 Quay Street, Porthgwarra",
        "registered_on": dt.date(2019, 4, 1),
    }
    base.update(over)
    return Operator(**base)  # type: ignore[arg-type]


def test_an_operator_reference_is_a_slug() -> None:
    with pytest.raises(Invalid, match="reference is a slug"):
        operator(ref="Pellow and Daughter")


def test_an_operator_has_a_name_on_the_licence() -> None:
    with pytest.raises(Invalid, match="name on the licence"):
        operator(name="   ")


def test_a_letter_is_addressed_to_somebody() -> None:
    with pytest.raises(Invalid, match="addressed to somebody"):
        operator(contact_name="  ")


def test_an_address_a_letter_cannot_go_to_is_refused() -> None:
    for written in ("office", "office@pellow", "office at pellow.example", ""):
        with pytest.raises(Invalid, match="a letter can go to"):
            operator(email=written)


def test_an_operator_has_an_address_on_the_register() -> None:
    with pytest.raises(Invalid, match="address on the register"):
        operator(address="   ")


def test_the_line_a_letter_is_addressed_to_names_both() -> None:
    assert operator().letter_to() == "R Pellow, Pellow and Daughter"


def test_a_new_person_to_write_to_returns_a_copy() -> None:
    changed = operator().with_contact("J Pellow", "jp@pellow.example")
    assert changed.contact_name == "J Pellow"
    assert changed.email == "jp@pellow.example"
    assert operator().contact_name == "R Pellow"


def test_a_new_contact_with_an_address_that_will_not_do_is_refused() -> None:
    with pytest.raises(Invalid, match="a letter can go to"):
        operator().with_contact("J Pellow", "not an address")


def test_a_new_address_on_the_register_returns_a_copy() -> None:
    assert operator().with_address("2 Quay Street").address == "2 Quay Street"


def test_the_years_on_the_register_are_whole_years() -> None:
    held = operator(registered_on=dt.date(2019, 4, 1))
    assert held.years_on_the_register(dt.date(2026, 3, 31)) == 6
    assert held.years_on_the_register(dt.date(2026, 4, 1)) == 7


def test_an_operator_registered_today_has_no_years_yet() -> None:
    held = operator(registered_on=dt.date(2026, 4, 1))
    assert held.years_on_the_register(dt.date(2026, 4, 1)) == 0
    assert held.years_on_the_register(dt.date(2025, 4, 1)) == 0
