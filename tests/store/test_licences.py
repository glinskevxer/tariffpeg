"""The register round trips a licence, particulars and all."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import AlreadyExists, Invalid, NotFound
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.store.db import Database
from tariffpeg.store.licences import (
    LicenceStore,
    decode_months,
    decode_value,
    encode_months,
    encode_value,
)


def make(serial: int = 4021, **over: object) -> Licence:
    base: dict[str, object] = {
        "serial": serial,
        "trading_name": "The Anchor Rooms",
        "operator_name": "Pellow and Daughter",
        "locality": "Porthgwarra",
        "period_start": dt.date(2025, 4, 1),
        "period_end": dt.date(2026, 3, 31),
        "particulars": {
            "grading_band": 3,
            "let_rooms": 9,
            "bed_spaces": 18,
            "lift": False,
            "shore_distance": 220,
        },
        "closed_months": frozenset({1, 2}),
    }
    base.update(over)
    return Licence(**base)  # type: ignore[arg-type]


def test_months_encode_sorted_and_deduplicated() -> None:
    assert encode_months([3, 1, 1, 2]) == "1,2,3"
    assert encode_months([]) == ""


def test_months_read_back_to_the_same_set() -> None:
    assert decode_months("1,2,3") == frozenset({1, 2, 3})
    assert decode_months("") == frozenset()
    assert decode_months("  ") == frozenset()


def test_a_flag_survives_the_trip_through_an_integer_column() -> None:
    assert encode_value("lift", True) == 1
    assert encode_value("lift", False) == 0
    assert decode_value("lift", 1) is True
    assert decode_value("lift", 0) is False


def test_a_count_stays_a_count_and_does_not_come_back_as_a_boolean() -> None:
    assert decode_value("let_rooms", 1) == 1
    assert decode_value("let_rooms", 1) is not True


def test_encoding_still_runs_the_kind_check() -> None:
    with pytest.raises(Invalid, match="yes or no"):
        encode_value("lift", 3)


def test_a_licence_round_trips_with_its_particulars(db: Database) -> None:
    store = LicenceStore(db)
    original = make()
    store.add(original)
    assert store.get(4021) == original


def test_a_licence_is_reachable_by_the_reference_on_the_plaque(db: Database) -> None:
    store = LicenceStore(db)
    licence = make()
    store.add(licence)
    assert store.by_ref(licence.ref) == licence


def test_a_reference_that_does_not_parse_reads_as_a_missing_licence(db: Database) -> None:
    store = LicenceStore(db)
    with pytest.raises(NotFound):
        store.by_ref("nonsense")


def test_adding_the_same_serial_twice_is_refused(db: Database) -> None:
    store = LicenceStore(db)
    store.add(make())
    with pytest.raises(AlreadyExists, match="already registered"):
        store.add(make())


def test_asking_for_a_licence_that_is_not_there_is_refused(db: Database) -> None:
    store = LicenceStore(db)
    with pytest.raises(NotFound, match="licence"):
        store.get(1)


def test_a_variation_is_written_over_the_register_entry(db: Database) -> None:
    store = LicenceStore(db)
    store.add(make())
    varied = store.get(4021).with_particular("lift", True).with_status(LicenceStatus.SUSPENDED)
    store.replace(varied)
    reread = store.get(4021)
    assert reread.particular("lift") is True
    assert reread.status is LicenceStatus.SUSPENDED


def test_a_variation_that_drops_a_particular_drops_it_from_the_table(db: Database) -> None:
    store = LicenceStore(db)
    store.add(make())
    trimmed = make(particulars={"grading_band": 3, "let_rooms": 9, "bed_spaces": 18})
    store.replace(trimmed)
    assert not store.get(4021).declares("lift")
    left = db.conn.execute("SELECT count(*) FROM licence_particular").fetchone()[0]
    assert left == 3


def test_replacing_a_licence_that_is_not_there_is_refused(db: Database) -> None:
    store = LicenceStore(db)
    with pytest.raises(NotFound):
        store.replace(make())


def test_the_register_lists_by_serial(db: Database) -> None:
    store = LicenceStore(db)
    for serial in (9, 4021, 100):
        store.add(make(serial))
    assert [licence.serial for licence in store.all()] == [9, 100, 4021]


def test_the_register_can_be_read_a_locality_at_a_time(db: Database) -> None:
    store = LicenceStore(db)
    store.add(make(1, locality="Porthgwarra"))
    store.add(make(2, locality="Sennen"))
    store.add(make(3, locality="Porthgwarra"))
    assert [licence.serial for licence in store.in_locality("Porthgwarra")] == [1, 3]
    assert store.in_locality("Nowhere") == ()


def test_the_register_can_be_read_a_status_at_a_time(db: Database) -> None:
    store = LicenceStore(db)
    store.add(make(1))
    store.add(make(2, status=LicenceStatus.LAPSED))
    assert [licence.serial for licence in store.with_status(LicenceStatus.ACTIVE)] == [1]
    assert [licence.serial for licence in store.with_status(LicenceStatus.LAPSED)] == [2]


def test_the_question_that_goes_across_licences_is_the_one_the_table_answers(
    db: Database,
) -> None:
    store = LicenceStore(db)
    store.add(make(1).with_particular("lift", True))
    store.add(make(2).with_particular("lift", False))
    store.add(make(3, particulars={"grading_band": 2, "let_rooms": 4, "bed_spaces": 8}))
    assert [licence.serial for licence in store.declaring("lift")] == [1, 2]
    assert [licence.serial for licence in store.declaring("lift", True)] == [1]
    assert [licence.serial for licence in store.declaring("lift", False)] == [2]


def test_asking_across_licences_for_something_that_is_not_a_particular_is_refused(
    db: Database,
) -> None:
    with pytest.raises(Invalid, match="no such particular"):
        LicenceStore(db).declaring("sauna")


def test_the_status_tally_counts_what_is_there(db: Database) -> None:
    store = LicenceStore(db)
    store.add(make(1))
    store.add(make(2))
    store.add(make(3, status=LicenceStatus.LAPSED))
    assert store.counts_by_status() == {"active": 2, "lapsed": 1}


def test_removing_a_licence_takes_its_particulars_with_it(db: Database) -> None:
    store = LicenceStore(db)
    store.add(make())
    store.remove(4021)
    assert not store.exists(4021)
    assert db.conn.execute("SELECT count(*) FROM licence_particular").fetchone()[0] == 0


def test_removing_a_licence_that_is_not_there_is_refused(db: Database) -> None:
    with pytest.raises(NotFound):
        LicenceStore(db).remove(4021)
