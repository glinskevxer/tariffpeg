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
from tariffpeg.errors import Conflict, NotFound
from tariffpeg.ids import capture_digest
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

    def keep_body(self, digest: str, body: bytes, at: dt.datetime) -> None:
        """Keep the bytes that were served, so the page can be replayed.

        The bytes are checked against the digest before they go in. A body that
        does not hash to the digest it is filed under is not evidence of
        anything, and the one place it could be caught is here.
        """
        if not self.exists(digest):
            raise NotFound("capture", digest)
        if capture_digest(body) != digest:
            raise Conflict("capture body", "these bytes do not hash to that digest")
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO capture_body (digest, body, stored_at) VALUES (?, ?, ?)",
                (digest, body, isoformat(at)),
            )

    def has_body(self, digest: str) -> bool:
        """Return whether the bytes for a capture are held."""
        row = self.db.conn.execute(
            "SELECT 1 FROM capture_body WHERE digest = ?", (digest,)
        ).fetchone()
        return row is not None

    def body_of(self, digest: str) -> bytes:
        """Return the bytes that were served, or refuse."""
        row = self.db.conn.execute(
            "SELECT body FROM capture_body WHERE digest = ?", (digest,)
        ).fetchone()
        if row is None:
            raise NotFound("capture body", digest)
        return bytes(row["body"])

    def bodies_held(self) -> int:
        """Return how many captures have their bytes kept."""
        return int(self.db.conn.execute("SELECT count(*) FROM capture_body").fetchone()[0])

    def bytes_held(self) -> int:
        """Return how many bytes of pages the store is carrying."""
        row = self.db.conn.execute("SELECT sum(length(body)) FROM capture_body").fetchone()
        return int(row[0] or 0)

    def body_problems(self) -> tuple[str, ...]:
        """Return every kept body that does not hash to the digest it is under.

        Nothing should ever be able to produce one of these. It is checked
        because a bundle exported from a store with one in it would be a bundle
        that verifies against itself and against nothing else.
        """
        rows = self.db.conn.execute(
            "SELECT digest, body FROM capture_body ORDER BY digest"
        ).fetchall()
        found: list[str] = []
        for row in rows:
            actual = capture_digest(bytes(row["body"]))
            if actual != str(row["digest"]):
                found.append(f"{row['digest']} is filed against bytes that hash to {actual}")
        return tuple(found)

    def forget_body(self, digest: str) -> None:
        """Drop the bytes for a capture, keeping the record that it was fetched."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM capture_body WHERE digest = ?", (digest,))
