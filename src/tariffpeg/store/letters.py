"""Reading and writing the correspondence register."""

from __future__ import annotations

import datetime as dt
import sqlite3

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.letter import Letter, Sent
from tariffpeg.store.db import Database

COLUMNS = (
    "reference",
    "operator_ref",
    "licence_serial",
    "kind",
    "sent_on",
    "subject",
    "body_digest",
    "replied_on",
)
"""The letter columns, in the order the table declares them."""

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
"""One question mark per column, for an insert."""

SELECT = f"SELECT {', '.join(COLUMNS)} FROM letter"


def hydrate(row: sqlite3.Row) -> Letter:
    """Build a letter out of a row."""
    replied = str(row["replied_on"])
    return Letter(
        reference=str(row["reference"]),
        operator_ref=str(row["operator_ref"]),
        licence_serial=int(row["licence_serial"]),
        kind=Sent(str(row["kind"])),
        sent_on=dt.date.fromisoformat(str(row["sent_on"])),
        subject=str(row["subject"]),
        body_digest=str(row["body_digest"]),
        replied_on=dt.date.fromisoformat(replied) if replied else None,
    )


def flatten(letter: Letter) -> tuple[object, ...]:
    """Return the row values for a letter, in column order."""
    return (
        letter.reference,
        letter.operator_ref,
        letter.licence_serial,
        str(letter.kind),
        letter.sent_on.isoformat(),
        letter.subject,
        letter.body_digest,
        letter.replied_on.isoformat() if letter.replied_on else "",
    )


class LetterStore:
    """The record of what went out and what came back."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, reference: str) -> bool:
        """Return whether this letter is on the register."""
        row = self.db.conn.execute(
            "SELECT 1 FROM letter WHERE reference = ?", (reference,)
        ).fetchone()
        return row is not None

    def add(self, letter: Letter) -> None:
        """Record that a letter went out."""
        if self.exists(letter.reference):
            raise AlreadyExists("letter", letter.reference)
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO letter ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})",
                flatten(letter),
            )

    def get(self, reference: str) -> Letter:
        """Return one letter, or refuse."""
        row = self.db.conn.execute(f"{SELECT} WHERE reference = ?", (reference,)).fetchone()
        if row is None:
            raise NotFound("letter", reference)
        return hydrate(row)

    def record_reply(self, reference: str, day: dt.date) -> Letter:
        """Record that the operator answered, and return the letter."""
        answered = self.get(reference).with_reply(day)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE letter SET replied_on = ? WHERE reference = ?",
                (day.isoformat(), reference),
            )
        return answered

    def for_licence(self, serial: int) -> tuple[Letter, ...]:
        """Return the letters about one premises, oldest first."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ? ORDER BY sent_on, reference", (serial,)
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def for_operator(self, ref: str) -> tuple[Letter, ...]:
        """Return the letters to one operator, oldest first."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE operator_ref = ? ORDER BY sent_on, reference", (ref,)
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def unanswered(self) -> tuple[Letter, ...]:
        """Return every letter nobody has answered, oldest first."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE replied_on = '' ORDER BY sent_on, reference"
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def overdue_on(
        self, day: dt.date, holidays: frozenset[dt.date] = frozenset()
    ) -> tuple[Letter, ...]:
        """Return every letter whose reply is late as at a day."""
        return tuple(letter for letter in self.unanswered() if letter.overdue_on(day, holidays))

    def count(self) -> int:
        """Return how many letters the register holds."""
        return int(self.db.conn.execute("SELECT count(*) FROM letter").fetchone()[0])
