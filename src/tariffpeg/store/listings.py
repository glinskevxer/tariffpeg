"""Reading and writing the listing register.

A channel numbers each property once, so a property reference is unique within a
channel and the store says so. Two licences pointed at one page is the mistake
this catches, and it is the mistake that puts one operator on the record for
what a guest said about another.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.listing import Listing
from tariffpeg.store.db import Database

COLUMNS = ("licence_serial", "channel", "path", "property_ref", "confirmed_on", "active", "note")
"""The listing columns, in the order the table declares them."""

SELECT = f"SELECT {', '.join(COLUMNS)} FROM listing"


def hydrate(row: sqlite3.Row) -> Listing:
    """Build a listing out of a row."""
    return Listing(
        licence_serial=int(row["licence_serial"]),
        channel=str(row["channel"]),
        path=str(row["path"]),
        property_ref=str(row["property_ref"]),
        confirmed_on=dt.date.fromisoformat(str(row["confirmed_on"])),
        active=bool(row["active"]),
        note=str(row["note"]),
    )


def flatten(listing: Listing) -> tuple[object, ...]:
    """Return the row values for a listing, in column order."""
    return (
        listing.licence_serial,
        listing.channel,
        listing.path,
        listing.property_ref,
        listing.confirmed_on.isoformat(),
        int(listing.active),
        listing.note,
    )


class ListingStore:
    """The register of which page is which premises."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, serial: int, channel: str) -> bool:
        """Return whether this premises is already listed on this channel."""
        row = self.db.conn.execute(
            "SELECT 1 FROM listing WHERE licence_serial = ? AND channel = ?", (serial, channel)
        ).fetchone()
        return row is not None

    def add(self, listing: Listing) -> None:
        """Record a listing."""
        if self.exists(listing.licence_serial, listing.channel):
            raise AlreadyExists("listing", listing.key)
        placeholders = ", ".join("?" for _ in COLUMNS)
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    f"INSERT INTO listing ({', '.join(COLUMNS)}) VALUES ({placeholders})",
                    flatten(listing),
                )
        except sqlite3.IntegrityError as err:
            raise AlreadyExists("property", f"{listing.channel}:{listing.property_ref}") from err

    def replace(self, listing: Listing) -> None:
        """Write a listing over the one already recorded."""
        if not self.exists(listing.licence_serial, listing.channel):
            raise NotFound("listing", listing.key)
        assignments = ", ".join(f"{column} = ?" for column in COLUMNS[2:])
        values = flatten(listing)
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE listing SET {assignments} WHERE licence_serial = ? AND channel = ?",
                (*values[2:], listing.licence_serial, listing.channel),
            )

    def get(self, serial: int, channel: str) -> Listing:
        """Return one listing, or refuse."""
        row = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ? AND channel = ?", (serial, channel)
        ).fetchone()
        if row is None:
            raise NotFound("listing", f"{serial}:{channel}")
        return hydrate(row)

    def for_licence(self, serial: int, active_only: bool = True) -> tuple[Listing, ...]:
        """Return the listings for one premises, by channel."""
        clause = " AND active = 1" if active_only else ""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ?{clause} ORDER BY channel", (serial,)
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def on_channel(self, channel: str, active_only: bool = True) -> tuple[Listing, ...]:
        """Return the listings on one channel, by licence."""
        clause = " AND active = 1" if active_only else ""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE channel = ?{clause} ORDER BY licence_serial", (channel,)
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def stale_on(self, day: dt.date) -> tuple[Listing, ...]:
        """Return the active listings whose confirmation has gone stale."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE active = 1 ORDER BY licence_serial, channel"
        ).fetchall()
        return tuple(listing for listing in map(hydrate, rows) if listing.stale_on(day))

    def remove(self, serial: int, channel: str) -> None:
        """Take a listing off the register."""
        if not self.exists(serial, channel):
            raise NotFound("listing", f"{serial}:{channel}")
        with self.db.transaction() as conn:
            conn.execute(
                "DELETE FROM listing WHERE licence_serial = ? AND channel = ?", (serial, channel)
            )
