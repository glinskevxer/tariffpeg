"""Reading and writing the register of licences.

Particulars live in their own table rather than in a blob column, because the
question the unit asks most often is the one that goes across licences: which
of these premises told us they have a lift.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Iterable, Mapping

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.ids import parse_licence_ref
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.particulars import ClaimKind, spec_for
from tariffpeg.store.db import Database

COLUMNS = (
    "serial",
    "trading_name",
    "operator_name",
    "locality",
    "period_start",
    "period_end",
    "closed_months",
    "status",
)
"""The licence columns, in the order the table declares them."""


def encode_months(months: Iterable[int]) -> str:
    """Render the closed months as the register writes them."""
    return ",".join(str(month) for month in sorted(set(months)))


def decode_months(text: str) -> frozenset[int]:
    """Read the closed months back off a row."""
    if not text.strip():
        return frozenset()
    return frozenset(int(part) for part in text.split(","))


def encode_value(key: str, value: bool | int) -> int:
    """Render a particular's value as the integer the table holds."""
    spec_for(key).validate(value)
    return int(value)


def decode_value(key: str, stored: int) -> bool | int:
    """Read a particular back, restoring the kind the order gives it."""
    spec = spec_for(key)
    if spec.kind is ClaimKind.FLAG:
        return bool(stored)
    return stored


class LicenceStore:
    """The register, as a table of licences and a table of particulars."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def _particulars(self, serial: int) -> dict[str, bool | int]:
        rows = self.db.conn.execute(
            "SELECT claim_key, value FROM licence_particular WHERE serial = ? ORDER BY claim_key",
            (serial,),
        ).fetchall()
        return {
            str(row["claim_key"]): decode_value(str(row["claim_key"]), int(row["value"]))
            for row in rows
        }

    def _hydrate(self, row: sqlite3.Row) -> Licence:
        serial = int(row["serial"])
        return Licence(
            serial=serial,
            trading_name=str(row["trading_name"]),
            operator_name=str(row["operator_name"]),
            locality=str(row["locality"]),
            period_start=dt.date.fromisoformat(str(row["period_start"])),
            period_end=dt.date.fromisoformat(str(row["period_end"])),
            particulars=self._particulars(serial),
            closed_months=decode_months(str(row["closed_months"])),
            status=LicenceStatus(str(row["status"])),
        )

    def _write_particulars(self, conn: sqlite3.Connection, licence: Licence) -> None:
        conn.execute("DELETE FROM licence_particular WHERE serial = ?", (licence.serial,))
        for key, value in sorted(licence.particulars.items()):
            conn.execute(
                "INSERT INTO licence_particular (serial, claim_key, kind, value)"
                " VALUES (?, ?, ?, ?)",
                (licence.serial, key, str(spec_for(key).kind), encode_value(key, value)),
            )

    def exists(self, serial: int) -> bool:
        """Return whether a serial is already on the register."""
        row = self.db.conn.execute("SELECT 1 FROM licence WHERE serial = ?", (serial,)).fetchone()
        return row is not None

    def add(self, licence: Licence) -> None:
        """Put a new licence on the register."""
        if self.exists(licence.serial):
            raise AlreadyExists("licence", licence.ref)
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO licence ({', '.join(COLUMNS)}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    licence.serial,
                    licence.trading_name,
                    licence.operator_name,
                    licence.locality,
                    licence.period_start.isoformat(),
                    licence.period_end.isoformat(),
                    encode_months(licence.closed_months),
                    str(licence.status),
                ),
            )
            self._write_particulars(conn, licence)

    def replace(self, licence: Licence) -> None:
        """Write a varied licence over the one on the register."""
        if not self.exists(licence.serial):
            raise NotFound("licence", licence.ref)
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE licence SET trading_name = ?, operator_name = ?, locality = ?,"
                " period_start = ?, period_end = ?, closed_months = ?, status = ?"
                " WHERE serial = ?",
                (
                    licence.trading_name,
                    licence.operator_name,
                    licence.locality,
                    licence.period_start.isoformat(),
                    licence.period_end.isoformat(),
                    encode_months(licence.closed_months),
                    str(licence.status),
                    licence.serial,
                ),
            )
            self._write_particulars(conn, licence)

    def get(self, serial: int) -> Licence:
        """Return a licence by serial, or refuse."""
        row = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM licence WHERE serial = ?", (serial,)
        ).fetchone()
        if row is None:
            raise NotFound("licence", str(serial))
        return self._hydrate(row)

    def by_ref(self, ref: str) -> Licence:
        """Return a licence by the reference printed on the plaque."""
        try:
            serial = parse_licence_ref(ref)
        except ValueError as err:
            raise NotFound("licence", ref) from err
        return self.get(serial)

    def all(self) -> tuple[Licence, ...]:
        """Return every licence on the register, by serial."""
        rows = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM licence ORDER BY serial"
        ).fetchall()
        return tuple(self._hydrate(row) for row in rows)

    def in_locality(self, locality: str) -> tuple[Licence, ...]:
        """Return the licences in one locality, by serial."""
        rows = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM licence WHERE locality = ? ORDER BY serial",
            (locality,),
        ).fetchall()
        return tuple(self._hydrate(row) for row in rows)

    def with_status(self, status: LicenceStatus) -> tuple[Licence, ...]:
        """Return the licences in one status, by serial."""
        rows = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM licence WHERE status = ? ORDER BY serial",
            (str(status),),
        ).fetchall()
        return tuple(self._hydrate(row) for row in rows)

    def declaring(self, key: str, value: bool | int | None = None) -> tuple[Licence, ...]:
        """Return the licences that declare a particular, optionally at a value."""
        spec_for(key)
        if value is None:
            rows = self.db.conn.execute(
                "SELECT serial FROM licence_particular WHERE claim_key = ? ORDER BY serial",
                (key,),
            ).fetchall()
        else:
            rows = self.db.conn.execute(
                "SELECT serial FROM licence_particular WHERE claim_key = ? AND value = ?"
                " ORDER BY serial",
                (key, encode_value(key, value)),
            ).fetchall()
        return tuple(self.get(int(row["serial"])) for row in rows)

    def counts_by_status(self) -> Mapping[str, int]:
        """Return how many licences sit in each status."""
        rows = self.db.conn.execute(
            "SELECT status, count(*) AS n FROM licence GROUP BY status ORDER BY status"
        ).fetchall()
        return {str(row["status"]): int(row["n"]) for row in rows}

    def remove(self, serial: int) -> None:
        """Take a licence off the register, particulars and all."""
        if not self.exists(serial):
            raise NotFound("licence", str(serial))
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM licence WHERE serial = ?", (serial,))
