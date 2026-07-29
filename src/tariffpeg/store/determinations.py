"""Reading and writing the ledger of minuted decisions."""

from __future__ import annotations

import sqlite3

from tariffpeg.clock import isoformat, parse_instant
from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.determination import Determination
from tariffpeg.model.outcome import parse_disposition
from tariffpeg.model.period import StayMonth
from tariffpeg.store.db import Database

COLUMNS = (
    "licence_serial",
    "decided_year",
    "decided_month",
    "disposition",
    "score",
    "access_score",
    "capped",
    "pack_version",
    "minuted_at",
    "officer",
)
"""The ledger columns, in the order the table declares them."""

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
"""One question mark per column, for an insert."""

SELECT = f"SELECT {', '.join(COLUMNS)} FROM determination"

ORDERED = " ORDER BY decided_year, decided_month, licence_serial"
"""How the ledger reads back, so two runs give the same answer."""


def hydrate(row: sqlite3.Row) -> Determination:
    """Build a minute out of a row."""
    return Determination(
        licence_serial=int(row["licence_serial"]),
        decided_at=StayMonth(int(row["decided_year"]), int(row["decided_month"])),
        disposition=parse_disposition(str(row["disposition"])),
        score=float(row["score"]),
        access_score=float(row["access_score"]),
        capped=bool(row["capped"]),
        pack_version=int(row["pack_version"]),
        minuted_at=parse_instant(str(row["minuted_at"])),
        officer=str(row["officer"]),
    )


def flatten(minute: Determination) -> tuple[object, ...]:
    """Return the row values for a minute, in column order."""
    return (
        minute.licence_serial,
        minute.decided_at.year,
        minute.decided_at.month,
        str(minute.disposition),
        minute.score,
        minute.access_score,
        int(minute.capped),
        minute.pack_version,
        isoformat(minute.minuted_at),
        minute.officer,
    )


class DeterminationStore:
    """The minutes the unit has taken, one per licence per month."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, serial: int, at: StayMonth) -> bool:
        """Return whether this month has already been minuted for this licence."""
        row = self.db.conn.execute(
            "SELECT 1 FROM determination WHERE licence_serial = ?"
            " AND decided_year = ? AND decided_month = ?",
            (serial, at.year, at.month),
        ).fetchone()
        return row is not None

    def record(self, minute: Determination) -> None:
        """Write a minute, refusing to overwrite one that is already taken.

        A minute is a record of what was decided, not a cache of what would be
        decided. Overwriting one silently is how the ledger stops being able to
        answer the question it was built for.
        """
        if self.exists(minute.licence_serial, minute.decided_at):
            raise AlreadyExists("determination", f"{minute.licence_serial}/{minute.decided_at}")
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO determination ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})",
                flatten(minute),
            )

    def get(self, serial: int, at: StayMonth) -> Determination:
        """Return one minute, or refuse."""
        row = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ? AND decided_year = ? AND decided_month = ?",
            (serial, at.year, at.month),
        ).fetchone()
        if row is None:
            raise NotFound("determination", f"{serial}/{at}")
        return hydrate(row)

    def for_licence(self, serial: int) -> tuple[Determination, ...]:
        """Return every minute taken about one licence, oldest month first."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ?{ORDERED}", (serial,)
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def at_month(self, at: StayMonth) -> tuple[Determination, ...]:
        """Return every minute taken for one month."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE decided_year = ? AND decided_month = ?{ORDERED}",
            (at.year, at.month),
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def all(self) -> tuple[Determination, ...]:
        """Return the whole ledger, oldest month first."""
        rows = self.db.conn.execute(f"{SELECT}{ORDERED}").fetchall()
        return tuple(hydrate(row) for row in rows)

    def latest_for(self, serial: int) -> Determination | None:
        """Return the most recently decided month for a licence, if there is one."""
        found = self.for_licence(serial)
        return found[-1] if found else None

    def previous_to(self, serial: int, at: StayMonth) -> Determination | None:
        """Return the minute before a month, if one was taken."""
        earlier = [item for item in self.for_licence(serial) if item.decided_at < at]
        return earlier[-1] if earlier else None

    def months(self) -> tuple[StayMonth, ...]:
        """Return the months the ledger has anything for, oldest first."""
        rows = self.db.conn.execute(
            "SELECT DISTINCT decided_year, decided_month FROM determination"
            " ORDER BY decided_year, decided_month"
        ).fetchall()
        return tuple(StayMonth(int(row[0]), int(row[1])) for row in rows)

    def count(self) -> int:
        """Return how many minutes the ledger holds."""
        row = self.db.conn.execute("SELECT count(*) FROM determination").fetchone()
        return int(row[0])
