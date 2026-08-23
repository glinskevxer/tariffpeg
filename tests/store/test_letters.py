"""The register holds what went out and what came back."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.letter import Letter, Sent
from tariffpeg.model.operator import Operator
from tariffpeg.store.db import Database
from tariffpeg.store.letters import COLUMNS, LetterStore, flatten
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.operators import OperatorStore
from tests.store.conftest import a_licence

DIGEST = "sha256:" + "c" * 64
SENT = dt.date(2026, 6, 1)
HELD = "pellow-and-daughter"


def letter(reference: str = "DE-2026-0044", **over: object) -> Letter:
    base: dict[str, object] = {
        "reference": reference,
        "operator_ref": HELD,
        "licence_serial": 4021,
        "kind": Sent.DESK_ENQUIRY,
        "sent_on": SENT,
        "subject": "The passenger lift at The Anchor Rooms",
        "body_digest": DIGEST,
    }
    base.update(over)
    return Letter(**base)  # type: ignore[arg-type]


@pytest.fixture
def store(db: Database) -> LetterStore:
    OperatorStore(db).add(
        Operator(HELD, "Pellow and Daughter", "R Pellow", "o@p.example", "1 Quay", SENT)
    )
    LicenceStore(db).add(a_licence(4021).with_operator(HELD))
    return LetterStore(db)


def test_flattening_produces_one_value_for_every_column() -> None:
    assert len(flatten(letter())) == len(COLUMNS)


def test_a_letter_round_trips_through_the_register(store: LetterStore) -> None:
    original = letter()
    store.add(original)
    assert store.get("DE-2026-0044") == original


def test_an_answered_letter_round_trips_with_its_reply(store: LetterStore) -> None:
    store.add(letter().with_reply(dt.date(2026, 6, 8)))
    assert store.get("DE-2026-0044").replied_on == dt.date(2026, 6, 8)


def test_the_same_reference_twice_is_refused(store: LetterStore) -> None:
    store.add(letter())
    with pytest.raises(AlreadyExists, match="letter"):
        store.add(letter())


def test_asking_for_a_letter_nobody_sent_is_refused(store: LetterStore) -> None:
    with pytest.raises(NotFound, match="letter"):
        store.get("DE-9999")


def test_a_reply_is_recorded_against_the_letter(store: LetterStore) -> None:
    store.add(letter())
    answered = store.record_reply("DE-2026-0044", dt.date(2026, 6, 8))
    assert answered.answered
    assert store.get("DE-2026-0044").replied_on == dt.date(2026, 6, 8)


def test_a_reply_to_a_letter_nobody_sent_is_refused(store: LetterStore) -> None:
    with pytest.raises(NotFound):
        store.record_reply("DE-9999", dt.date(2026, 6, 8))


def test_the_letters_about_a_premises_come_back_oldest_first(store: LetterStore) -> None:
    store.add(letter("DE-2", sent_on=dt.date(2026, 7, 1)))
    store.add(letter("DE-1"))
    assert [held.reference for held in store.for_licence(4021)] == ["DE-1", "DE-2"]
    assert store.for_licence(9999) == ()


def test_the_letters_to_an_operator_come_back_oldest_first(store: LetterStore) -> None:
    store.add(letter("DE-2", sent_on=dt.date(2026, 7, 1)))
    store.add(letter("DE-1"))
    assert [held.reference for held in store.for_operator(HELD)] == ["DE-1", "DE-2"]
    assert store.for_operator("nowhere") == ()


def test_the_unanswered_letters_come_back_on_their_own(store: LetterStore) -> None:
    store.add(letter("DE-1"))
    store.add(letter("DE-2").with_reply(dt.date(2026, 6, 8)))
    assert [held.reference for held in store.unanswered()] == ["DE-1"]


def test_the_letters_whose_reply_is_late_come_back(store: LetterStore) -> None:
    store.add(letter("DE-1"))
    due = letter("DE-1").due_on()
    assert store.overdue_on(due) == ()
    late = store.overdue_on(due + dt.timedelta(days=1))
    assert [held.reference for held in late] == ["DE-1"]


def test_an_answered_letter_never_shows_up_as_late(store: LetterStore) -> None:
    store.add(letter("DE-1").with_reply(dt.date(2026, 6, 8)))
    assert store.overdue_on(dt.date(2027, 1, 1)) == ()


def test_a_holiday_pushes_a_letter_out_of_the_late_list(store: LetterStore) -> None:
    store.add(letter("DE-1"))
    due = letter("DE-1").due_on()
    holidays = frozenset({due})
    assert store.overdue_on(due + dt.timedelta(days=1), holidays) == ()


def test_the_register_counts_what_it_holds(store: LetterStore) -> None:
    assert store.count() == 0
    store.add(letter("DE-1"))
    store.add(letter("DE-2"))
    assert store.count() == 2


def test_a_letter_to_an_operator_nobody_registered_is_refused(store: LetterStore) -> None:
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        store.add(letter(operator_ref="nowhere"))


def test_dropping_a_licence_takes_its_letters_with_it(store: LetterStore, db: Database) -> None:
    store.add(letter())
    LicenceStore(db).remove(4021)
    assert store.count() == 0


def test_the_reminders_sent_about_a_licence_are_counted(store: LetterStore) -> None:
    assert store.chased(4021) == 0
    store.add(letter("DE-1", kind=Sent.DESK_ENQUIRY))
    store.add(letter("RM-1", kind=Sent.REMINDER))
    store.add(letter("RM-2", kind=Sent.REMINDER))
    assert store.chased(4021) == 2
    assert len(store.of_kind(4021, Sent.DESK_ENQUIRY)) == 1


def test_a_licence_nobody_wrote_to_has_no_letters_of_any_kind(store: LetterStore) -> None:
    assert store.of_kind(9999, Sent.REMINDER) == ()
