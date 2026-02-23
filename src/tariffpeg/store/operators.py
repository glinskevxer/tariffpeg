"""Reading and writing the operator register."""

from __future__ import annotations

import datetime as dt
import sqlite3

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.operator import Operator
from tariffpeg.store.db import Database

COLUMNS = ("ref", "name", "contact_name", "email", "address", "registered_on", "note")
"""The operator columns, in the order the table declares them."""

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
"""One question mark per column, for an insert."""

ASSIGNMENTS = ", ".join(f"{column} = ?" for column in COLUMNS[1:])
"""The columns an update writes, which is every one but the key."""

SELECT = f"SELECT {', '.join(COLUMNS)} FROM operator"


def hydrate(row: sqlite3.Row) -> Operator:
    """Build an operator out of a row."""
    return Operator(
        ref=str(row["ref"]),
        name=str(row["name"]),
        contact_name=str(row["contact_name"]),
        email=str(row["email"]),
        address=str(row["address"]),
        registered_on=dt.date.fromisoformat(str(row["registered_on"])),
        note=str(row["note"]),
    )


def flatten(operator: Operator) -> tuple[object, ...]:
    """Return the row values for an operator, in column order."""
    return (
        operator.ref,
        operator.name,
        operator.contact_name,
        operator.email,
        operator.address,
        operator.registered_on.isoformat(),
        operator.note,
    )


class OperatorStore:
    """The register of who holds the licences."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, ref: str) -> bool:
        """Return whether this operator is on the register."""
        row = self.db.conn.execute("SELECT 1 FROM operator WHERE ref = ?", (ref,)).fetchone()
        return row is not None

    def add(self, operator: Operator) -> None:
        """Put an operator on the register."""
        if self.exists(operator.ref):
            raise AlreadyExists("operator", operator.ref)
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO operator ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})",
                flatten(operator),
            )

    def replace(self, operator: Operator) -> None:
        """Write new details over the ones on the register."""
        if not self.exists(operator.ref):
            raise NotFound("operator", operator.ref)
        values = flatten(operator)
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE operator SET {ASSIGNMENTS} WHERE ref = ?", (*values[1:], operator.ref)
            )

    def get(self, ref: str) -> Operator:
        """Return an operator by reference, or refuse."""
        row = self.db.conn.execute(f"{SELECT} WHERE ref = ?", (ref,)).fetchone()
        if row is None:
            raise NotFound("operator", ref)
        return hydrate(row)

    def all(self) -> tuple[Operator, ...]:
        """Return every operator on the register, by reference."""
        rows = self.db.conn.execute(f"{SELECT} ORDER BY ref").fetchall()
        return tuple(hydrate(row) for row in rows)

    def serials_for(self, ref: str) -> tuple[int, ...]:
        """Return the licences this operator holds, by serial."""
        rows = self.db.conn.execute(
            "SELECT serial FROM licence WHERE operator_ref = ? ORDER BY serial", (ref,)
        ).fetchall()
        return tuple(int(row["serial"]) for row in rows)

    def holding_more_than(self, count: int) -> tuple[Operator, ...]:
        """Return the operators holding more licences than a given number."""
        return tuple(
            operator for operator in self.all() if len(self.serials_for(operator.ref)) > count
        )

    def remove(self, ref: str) -> None:
        """Take an operator off the register."""
        if not self.exists(ref):
            raise NotFound("operator", ref)
        if self.serials_for(ref):
            raise AlreadyExists("licences", ref)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM operator WHERE ref = ?", (ref,))
