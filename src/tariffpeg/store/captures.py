"""Reading and writing captures, which is the chain of custody.

A capture is written once and never updated. Fetching the same page twice with
the same bytes coming back produces the same digest, so the second write is a
no operation rather than a conflict, and the first fetch time is the one that
stands.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from tariffpeg.clock import isoformat, parse_instant
from tariffpeg.errors import NotFound
from tariffpeg.model.capture import Capture
from tariffpeg.store.db import Database

COLUMNS = (
    "digest",
    "channel",
    "url",
    "final_url",
    "status",
    "fetched_at",
    "byte_count",
    "elapsed_ms",
    "profile_key",
    "licence_serial",
    "etag",
)
"""The capture columns, in the order the table declares them."""


PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
"""One question mark per column, for an insert."""


def hydrate(row: sqlite3.Row) -> Capture:
    """Build a capture out of a row."""
    serial = row["licence_serial"]
    return Capture(
        digest=str(row["digest"]),
        channel=str(row["channel"]),
        url=str(row["url"]),
        final_url=str(row["final_url"]),
        status=int(row["status"]),
        fetched_at=parse_instant(str(row["fetched_at"])),
        byte_count=int(row["byte_count"]),
        profile_key=str(row["profile_key"]),
        elapsed_ms=int(row["elapsed_ms"]),
        licence_serial=None if serial is None else int(serial),
        etag=str(row["etag"]),
    )


def flatten(capture: Capture) -> tuple[object, ...]:
    """Return the row values for a capture, in column order."""
    return (
        capture.digest,
        capture.channel,
        capture.url,
        capture.final_url,
        capture.status,
        isoformat(capture.fetched_at),
        capture.byte_count,
        capture.elapsed_ms,
        capture.profile_key,
        capture.licence_serial,
        capture.etag,
    )


class CaptureStore:
    """The register of what was fetched and when."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, digest: str) -> bool:
        """Return whether these bytes have been recorded before."""
        row = self.db.conn.execute("SELECT 1 FROM capture WHERE digest = ?", (digest,)).fetchone()
        return row is not None

    def record(self, capture: Capture) -> bool:
        """Record a capture, returning whether it was new.

        The same bytes fetched twice keep the first fetch time. That is the one
        the case file quotes, and moving it forward would quietly rewrite when
        the unit first saw a thing it is relying on.
        """
        if self.exists(capture.digest):
            return False
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO capture ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})",
                flatten(capture),
            )
        return True

    def get(self, digest: str) -> Capture:
        """Return a capture by digest, or refuse."""
        row = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM capture WHERE digest = ?", (digest,)
        ).fetchone()
        if row is None:
            raise NotFound("capture", digest)
        return hydrate(row)

    def for_channel(self, channel: str) -> tuple[Capture, ...]:
        """Return the captures from one channel, oldest first."""
        rows = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM capture WHERE channel = ? ORDER BY fetched_at,"
            " digest",
            (channel,),
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def for_licence(self, serial: int) -> tuple[Capture, ...]:
        """Return the captures taken against one licence, oldest first."""
        rows = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM capture WHERE licence_serial = ?"
            " ORDER BY fetched_at, digest",
            (serial,),
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def latest_for_url(self, url: str) -> Capture | None:
        """Return the most recent capture of a url, or nothing."""
        row = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM capture WHERE url = ?"
            " ORDER BY fetched_at DESC, digest LIMIT 1",
            (url,),
        ).fetchone()
        return None if row is None else hydrate(row)

    def count(self) -> int:
        """Return how many captures the store holds."""
        return int(self.db.conn.execute("SELECT count(*) FROM capture").fetchone()[0])

    def spent_on(self, channel: str, day: dt.date) -> int:
        """Return how many captures were taken from a channel on one UTC day."""
        row = self.db.conn.execute(
            "SELECT count(*) FROM capture WHERE channel = ? AND substr(fetched_at, 1, 10) = ?",
            (channel, day.isoformat()),
        ).fetchone()
        return int(row[0])
