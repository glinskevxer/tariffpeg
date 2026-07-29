"""The ledger refuses to be told twice what was decided once."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.determination import Determination
from tariffpeg.model.outcome import Disposition
from tariffpeg.model.period import StayMonth
from tariffpeg.store.db import Database
from tariffpeg.store.determinations import COLUMNS, DeterminationStore, flatten
from tariffpeg.store.licences import LicenceStore
from tests.store.conftest import a_licence

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


@pytest.fixture
def store(db: Database) -> DeterminationStore:
    LicenceStore(db).add(a_licence())
    return DeterminationStore(db)


def test_flattening_produces_one_value_for_every_column() -> None:
    assert len(flatten(minute())) == len(COLUMNS)


def test_a_minute_round_trips_through_the_ledger(store: DeterminationStore) -> None:
    store.record(minute())
    assert store.get(4021, AT) == minute()


def test_a_capped_minute_round_trips_as_capped(store: DeterminationStore) -> None:
    store.record(minute(capped=True))
    assert store.get(4021, AT).capped


def test_minuting_the_same_month_twice_is_refused(store: DeterminationStore) -> None:
    store.record(minute())
    with pytest.raises(AlreadyExists, match="determination"):
        store.record(minute(disposition=Disposition.URGENT))
    assert store.get(4021, AT).disposition is Disposition.DESK_ENQUIRY


def test_asking_for_a_month_nobody_minuted_is_refused(store: DeterminationStore) -> None:
    with pytest.raises(NotFound, match="determination"):
        store.get(4021, AT)


def test_a_licence_that_is_not_on_the_register_cannot_be_minuted(db: Database) -> None:
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        DeterminationStore(db).record(minute())


def test_the_minutes_for_a_licence_come_back_oldest_month_first(
    store: DeterminationStore,
) -> None:
    store.record(minute(decided_at=StayMonth(2025, 10)))
    store.record(minute())
    assert [item.decided_at for item in store.for_licence(4021)] == [AT, StayMonth(2025, 10)]


def test_a_month_reads_back_every_licence_minuted_in_it(
    store: DeterminationStore, db: Database
) -> None:
    LicenceStore(db).add(a_licence(serial=4022))
    store.record(minute())
    store.record(minute(licence_serial=4022))
    store.record(minute(decided_at=StayMonth(2025, 10)))
    assert [item.licence_serial for item in store.at_month(AT)] == [4021, 4022]


def test_the_whole_ledger_reads_back_oldest_month_first(store: DeterminationStore) -> None:
    store.record(minute(decided_at=StayMonth(2025, 11)))
    store.record(minute())
    assert store.count() == 2
    assert [item.decided_at for item in store.all()] == [AT, StayMonth(2025, 11)]


def test_the_latest_minute_is_the_one_for_the_newest_month(store: DeterminationStore) -> None:
    assert store.latest_for(4021) is None
    store.record(minute())
    store.record(minute(decided_at=StayMonth(2025, 12)))
    latest = store.latest_for(4021)
    assert latest is not None
    assert latest.decided_at == StayMonth(2025, 12)


def test_the_minute_before_a_month_is_the_newest_one_that_came_earlier(
    store: DeterminationStore,
) -> None:
    store.record(minute(decided_at=StayMonth(2025, 7)))
    store.record(minute(decided_at=StayMonth(2025, 8)))
    found = store.previous_to(4021, StayMonth(2025, 9))
    assert found is not None
    assert found.decided_at == StayMonth(2025, 8)


def test_there_is_no_minute_before_the_first_one(store: DeterminationStore) -> None:
    store.record(minute())
    assert store.previous_to(4021, AT) is None


def test_the_ledger_says_which_months_it_holds_anything_for(
    store: DeterminationStore,
) -> None:
    assert store.months() == ()
    store.record(minute(decided_at=StayMonth(2025, 11)))
    store.record(minute())
    assert store.months() == (AT, StayMonth(2025, 11))


def test_a_month_nobody_minuted_reads_back_empty(store: DeterminationStore) -> None:
    assert store.at_month(AT) == ()
    assert store.for_licence(4021) == ()
