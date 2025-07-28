"""An operator who fixed the lift twice has had it working since the later of the two."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.period import StayMonth
from tariffpeg.model.remediation import Remediation
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.remediations import COLUMNS, RemediationStore, flatten


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


@pytest.fixture
def store(stocked: Database) -> RemediationStore:
    return RemediationStore(stocked)


def test_flattening_produces_one_value_for_every_column() -> None:
    assert len(flatten(notice())) == len(COLUMNS)


def test_a_notice_round_trips_through_the_file(store: RemediationStore) -> None:
    original = notice().accept("the lift certificate was produced")
    store.add(original)
    assert store.get(4021, "lift", "RN-2026-0118") == original


def test_the_same_notice_twice_is_refused(store: RemediationStore) -> None:
    store.add(notice())
    with pytest.raises(AlreadyExists, match="remediation"):
        store.add(notice())


def test_asking_for_a_notice_nobody_filed_is_refused(store: RemediationStore) -> None:
    with pytest.raises(NotFound, match="remediation"):
        store.get(4021, "lift", "RN-9999")


def test_a_decision_is_written_over_the_notice_on_file(store: RemediationStore) -> None:
    store.add(notice())
    store.replace(store.get(4021, "lift", "RN-2026-0118").accept("certificate seen"))
    assert store.get(4021, "lift", "RN-2026-0118").accepted


def test_writing_over_a_notice_nobody_filed_is_refused(store: RemediationStore) -> None:
    with pytest.raises(NotFound):
        store.replace(notice())


def test_the_notices_for_a_licence_come_back_by_particular(store: RemediationStore) -> None:
    store.add(notice())
    store.add(notice(claim_key="breakfast_included", reference="RN-2026-0200"))
    assert [item.claim_key for item in store.for_licence(4021)] == [
        "breakfast_included",
        "lift",
    ]


def test_only_the_accepted_notices_come_back_when_that_is_asked_for(
    store: RemediationStore,
) -> None:
    store.add(notice())
    store.add(notice(reference="RN-2026-0200").accept("seen"))
    accepted = store.for_licence(4021, accepted_only=True)
    assert [item.reference for item in accepted] == ["RN-2026-0200"]


def test_the_notice_that_reaches_furthest_forward_is_the_one_that_counts(
    store: RemediationStore,
) -> None:
    store.add(notice(reference="RN-A", effective_from=StayMonth(2026, 1)).accept("seen"))
    store.add(notice(reference="RN-B", effective_from=StayMonth(2026, 3)).accept("seen"))
    latest = store.latest_for(4021, "lift")
    assert latest is not None
    assert latest.reference == "RN-B"


def test_a_notice_nobody_accepted_never_becomes_the_one_that_counts(
    store: RemediationStore,
) -> None:
    store.add(notice(reference="RN-A", effective_from=StayMonth(2026, 3)))
    assert store.latest_for(4021, "lift") is None


def test_a_particular_with_no_notice_has_no_latest(store: RemediationStore) -> None:
    assert store.latest_for(4021, "breakfast_included") is None


def test_a_notice_can_be_taken_off_file(store: RemediationStore) -> None:
    store.add(notice())
    store.remove(4021, "lift", "RN-2026-0118")
    assert not store.exists(4021, "lift", "RN-2026-0118")
    with pytest.raises(NotFound):
        store.remove(4021, "lift", "RN-2026-0118")


def test_dropping_a_licence_takes_its_notices_with_it(
    store: RemediationStore, stocked: Database
) -> None:
    store.add(notice())
    LicenceStore(stocked).remove(4021)
    assert store.for_licence(4021) == ()
