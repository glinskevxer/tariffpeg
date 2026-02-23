"""One operator holds several licences often enough that the register keeps them apart."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.operator import Operator
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.operators import COLUMNS, OperatorStore, flatten
from tests.store.conftest import a_licence

HELD = "pellow-and-daughter"


def operator(ref: str = HELD, **over: object) -> Operator:
    base: dict[str, object] = {
        "ref": ref,
        "name": "Pellow and Daughter",
        "contact_name": "R Pellow",
        "email": "office@pellow.example",
        "address": "1 Quay Street, Porthgwarra",
        "registered_on": dt.date(2019, 4, 1),
    }
    base.update(over)
    return Operator(**base)  # type: ignore[arg-type]


def test_flattening_produces_one_value_for_every_column() -> None:
    assert len(flatten(operator())) == len(COLUMNS)


def test_an_operator_round_trips_through_the_register(db: Database) -> None:
    store = OperatorStore(db)
    original = operator(note="took over the lease in 2019")
    store.add(original)
    assert store.get(HELD) == original


def test_the_same_reference_twice_is_refused(db: Database) -> None:
    store = OperatorStore(db)
    store.add(operator())
    with pytest.raises(AlreadyExists, match="operator"):
        store.add(operator())


def test_asking_for_an_operator_nobody_registered_is_refused(db: Database) -> None:
    with pytest.raises(NotFound, match="operator"):
        OperatorStore(db).get("nowhere")


def test_new_details_are_written_over_the_old_ones(db: Database) -> None:
    store = OperatorStore(db)
    store.add(operator())
    store.replace(store.get(HELD).with_contact("J Pellow", "jp@pellow.example"))
    assert store.get(HELD).contact_name == "J Pellow"


def test_replacing_an_operator_nobody_registered_is_refused(db: Database) -> None:
    with pytest.raises(NotFound):
        OperatorStore(db).replace(operator())


def test_the_register_lists_the_operators_by_reference(db: Database) -> None:
    store = OperatorStore(db)
    for ref in ("trewin-lets", "angove-rooms", HELD):
        store.add(operator(ref))
    assert [held.ref for held in store.all()] == ["angove-rooms", HELD, "trewin-lets"]


def test_the_licences_an_operator_holds_come_back(db: Database) -> None:
    OperatorStore(db).add(operator())
    licences = LicenceStore(db)
    licences.add(a_licence(4021).with_operator(HELD))
    licences.add(a_licence(5000).with_operator(HELD))
    licences.add(a_licence(6000))
    assert OperatorStore(db).serials_for(HELD) == (4021, 5000)
    assert [held.serial for held in licences.for_operator(HELD)] == [4021, 5000]


def test_an_operator_with_no_licences_holds_nothing(db: Database) -> None:
    OperatorStore(db).add(operator())
    assert OperatorStore(db).serials_for(HELD) == ()


def test_the_operators_holding_more_than_a_number_come_back(db: Database) -> None:
    store = OperatorStore(db)
    store.add(operator())
    store.add(operator("trewin-lets"))
    licences = LicenceStore(db)
    licences.add(a_licence(4021).with_operator(HELD))
    licences.add(a_licence(5000).with_operator(HELD))
    licences.add(a_licence(6000).with_operator("trewin-lets"))
    assert [held.ref for held in store.holding_more_than(1)] == [HELD]
    assert len(store.holding_more_than(0)) == 2


def test_an_operator_can_be_taken_off_the_register(db: Database) -> None:
    store = OperatorStore(db)
    store.add(operator())
    store.remove(HELD)
    assert not store.exists(HELD)
    with pytest.raises(NotFound):
        store.remove(HELD)


def test_an_operator_still_holding_a_licence_cannot_be_taken_off(db: Database) -> None:
    store = OperatorStore(db)
    store.add(operator())
    LicenceStore(db).add(a_licence(4021).with_operator(HELD))
    with pytest.raises(AlreadyExists, match="licences"):
        store.remove(HELD)


def test_a_licence_carries_the_operator_it_was_tied_to(db: Database) -> None:
    OperatorStore(db).add(operator())
    licences = LicenceStore(db)
    licences.add(a_licence(4021).with_operator(HELD))
    assert licences.get(4021).operator_ref == HELD


def test_a_licence_tied_to_nobody_carries_an_empty_reference(db: Database) -> None:
    LicenceStore(db).add(a_licence(4021))
    assert LicenceStore(db).get(4021).operator_ref == ""
