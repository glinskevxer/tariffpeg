"""Reading and writing remediation notices."""

from __future__ import annotations

import datetime as dt
import sqlite3

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.period import StayMonth
from tariffpeg.model.remediation import Remediation
from tariffpeg.store.db import Database

COLUMNS = (
    "licence_serial",
    "claim_key",
    "reference",
    "filed_on",
    "effective_year",
    "effective_month",
    "accepted",
    "note",
)
"""The remediation columns, in the order the table declares them."""


PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
"""One question mark per column, for an insert."""

SELECT = f"SELECT {', '.join(COLUMNS)} FROM remediation"


def hydrate(row: sqlite3.Row) -> Remediation:
    """Build a notice out of a row."""
    return Remediation(
        licence_serial=int(row["licence_serial"]),
        claim_key=str(row["claim_key"]),
        reference=str(row["reference"]),
        filed_on=dt.date.fromisoformat(str(row["filed_on"])),
        effective_from=StayMonth(int(row["effective_year"]), int(row["effective_month"])),
        accepted=bool(row["accepted"]),
        note=str(row["note"]),
    )


def flatten(notice: Remediation) -> tuple[object, ...]:
    """Return the row values for a notice, in column order."""
    return (
        notice.licence_serial,
        notice.claim_key,
        notice.reference,
        notice.filed_on.isoformat(),
        notice.effective_from.year,
        notice.effective_from.month,
        int(notice.accepted),
        notice.note,
    )


class RemediationStore:
    """The notices operators have filed."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, serial: int, claim_key: str, reference: str) -> bool:
        """Return whether this notice is already on file."""
        row = self.db.conn.execute(
            "SELECT 1 FROM remediation WHERE licence_serial = ? AND claim_key = ?"
            " AND reference = ?",
            (serial, claim_key, reference),
        ).fetchone()
        return row is not None

    def add(self, notice: Remediation) -> None:
        """Put a notice on file."""
        if self.exists(notice.licence_serial, notice.claim_key, notice.reference):
            raise AlreadyExists("remediation", notice.key)
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO remediation ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})",
                flatten(notice),
            )

    def replace(self, notice: Remediation) -> None:
        """Write a decision over the notice already on file."""
        if not self.exists(notice.licence_serial, notice.claim_key, notice.reference):
            raise NotFound("remediation", notice.key)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE remediation SET filed_on = ?, effective_year = ?, effective_month = ?,"
                " accepted = ?, note = ?"
                " WHERE licence_serial = ? AND claim_key = ? AND reference = ?",
                (
                    notice.filed_on.isoformat(),
                    notice.effective_from.year,
                    notice.effective_from.month,
                    int(notice.accepted),
                    notice.note,
                    notice.licence_serial,
                    notice.claim_key,
                    notice.reference,
                ),
            )

    def get(self, serial: int, claim_key: str, reference: str) -> Remediation:
        """Return one notice, or refuse."""
        row = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ? AND claim_key = ? AND reference = ?",
            (serial, claim_key, reference),
        ).fetchone()
        if row is None:
            raise NotFound("remediation", f"{serial}:{claim_key}:{reference}")
        return hydrate(row)

    def for_licence(self, serial: int, accepted_only: bool = False) -> tuple[Remediation, ...]:
        """Return the notices on file for a licence, by particular."""
        clause = " AND accepted = 1" if accepted_only else ""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ?{clause} ORDER BY claim_key, reference",
            (serial,),
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def latest_for(self, serial: int, claim_key: str) -> Remediation | None:
        """Return the accepted notice that reaches furthest forward for a particular.

        The one that reaches furthest forward is the one that matters. An
        operator who fixed the lift twice has had it working since the later of
        the two, whatever the earlier notice said.
        """
        rows = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ? AND claim_key = ? AND accepted = 1"
            " ORDER BY effective_year DESC, effective_month DESC, reference LIMIT 1",
            (serial, claim_key),
        ).fetchall()
        return hydrate(rows[0]) if rows else None

    def remove(self, serial: int, claim_key: str, reference: str) -> None:
        """Take a notice off file."""
        if not self.exists(serial, claim_key, reference):
            raise NotFound("remediation", f"{serial}:{claim_key}:{reference}")
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM remediation WHERE licence_serial = ? AND claim_key = ?"
                " AND reference = ?",
                (serial, claim_key, reference),
            )
