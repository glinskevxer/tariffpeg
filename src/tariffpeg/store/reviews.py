"""Reading and writing reviews.

A review is written once. Seeing it again on a later harvest is normal, and the
second write leaves the first seen date alone: the sampling regime counts when
the unit first had a review, not when it last happened to look at the page.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Mapping

from tariffpeg.clock import isoformat, parse_instant
from tariffpeg.errors import NotFound
from tariffpeg.ids import review_key
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.model.review import Review
from tariffpeg.store.db import Database

COLUMNS = (
    "review_key",
    "channel",
    "channel_review_id",
    "licence_serial",
    "stay_year",
    "stay_month",
    "unit_points",
    "raw_score",
    "title",
    "body",
    "reviewer_initials",
    "room_class",
    "language",
    "submitted",
    "operator_response",
    "capture_digest",
    "profile_key",
    "first_seen",
)
"""The review columns, in the order the table declares them."""


PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
"""One question mark per column, for an insert."""

SELECT = f"SELECT {', '.join(COLUMNS)} FROM review"


def hydrate(row: sqlite3.Row) -> Review:
    """Build a review out of a row."""
    submitted = str(row["submitted"])
    return Review(
        channel=str(row["channel"]),
        channel_review_id=str(row["channel_review_id"]),
        licence_serial=int(row["licence_serial"]),
        stay=StayMonth(int(row["stay_year"]), int(row["stay_month"])),
        unit_points=int(row["unit_points"]),
        raw_score=str(row["raw_score"]),
        body=str(row["body"]),
        capture_digest=str(row["capture_digest"]),
        profile_key=str(row["profile_key"]),
        title=str(row["title"]),
        reviewer_initials=str(row["reviewer_initials"]),
        room_class=str(row["room_class"]),
        language=str(row["language"]),
        submitted=dt.date.fromisoformat(submitted) if submitted else None,
        operator_response=str(row["operator_response"]),
    )


def flatten(review: Review, first_seen: dt.datetime) -> tuple[object, ...]:
    """Return the row values for a review, in column order."""
    return (
        review.key,
        review.channel,
        review.channel_review_id,
        review.licence_serial,
        review.stay.year,
        review.stay.month,
        review.unit_points,
        review.raw_score,
        review.title,
        review.body,
        review.reviewer_initials,
        review.room_class,
        review.language,
        review.submitted.isoformat() if review.submitted else "",
        review.operator_response,
        review.capture_digest,
        review.profile_key,
        isoformat(first_seen),
    )


class ReviewStore:
    """The reviews the unit has collected, by licence and by channel."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, key: str) -> bool:
        """Return whether this review is already held."""
        row = self.db.conn.execute("SELECT 1 FROM review WHERE review_key = ?", (key,)).fetchone()
        return row is not None

    def add(self, review: Review, first_seen: dt.datetime) -> bool:
        """Hold a review, returning whether it was new."""
        if self.exists(review.key):
            return False
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO review ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})",
                flatten(review, first_seen),
            )
        return True

    def get(self, key: str) -> Review:
        """Return a review by its store key, or refuse."""
        row = self.db.conn.execute(f"{SELECT} WHERE review_key = ?", (key,)).fetchone()
        if row is None:
            raise NotFound("review", key)
        return hydrate(row)

    def on_channel(self, channel: str, channel_review_id: str) -> Review:
        """Return a review by the way its own channel numbers it."""
        return self.get(review_key(channel, channel_review_id))

    def first_seen(self, key: str) -> dt.datetime:
        """Return when the unit first held this review."""
        row = self.db.conn.execute(
            "SELECT first_seen FROM review WHERE review_key = ?", (key,)
        ).fetchone()
        if row is None:
            raise NotFound("review", key)
        return parse_instant(str(row["first_seen"]))

    def for_licence(self, serial: int) -> tuple[Review, ...]:
        """Return every review held against a licence, oldest stay first."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ? ORDER BY stay_year, stay_month, review_key",
            (serial,),
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def between(self, serial: int, start: StayMonth, end: StayMonth) -> tuple[Review, ...]:
        """Return the reviews for a licence with stays inside a range of months."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE licence_serial = ?"
            " AND (stay_year * 12 + stay_month - 1) BETWEEN ? AND ?"
            " ORDER BY stay_year, stay_month, review_key",
            (serial, start.ordinal, end.ordinal),
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def for_channel(self, channel: str) -> tuple[Review, ...]:
        """Return every review held from one channel."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE channel = ? ORDER BY review_key", (channel,)
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def channels_for(self, serial: int) -> tuple[str, ...]:
        """Return the channels that have given up reviews for a licence."""
        rows = self.db.conn.execute(
            "SELECT DISTINCT channel FROM review WHERE licence_serial = ? ORDER BY channel",
            (serial,),
        ).fetchall()
        return tuple(str(row["channel"]) for row in rows)

    def count_for(self, serial: int) -> int:
        """Return how many reviews are held against a licence."""
        row = self.db.conn.execute(
            "SELECT count(*) FROM review WHERE licence_serial = ?", (serial,)
        ).fetchone()
        return int(row[0])

    def counts_by_month(self, serial: int) -> Mapping[StayMonth, int]:
        """Return how many reviews sit in each stay month for a licence."""
        rows = self.db.conn.execute(
            "SELECT stay_year, stay_month, count(*) AS n FROM review WHERE licence_serial = ?"
            " GROUP BY stay_year, stay_month ORDER BY stay_year, stay_month",
            (serial,),
        ).fetchall()
        return {StayMonth(int(r["stay_year"]), int(r["stay_month"])): int(r["n"]) for r in rows}

    def counts_by_season(self, serial: int) -> Mapping[Season, int]:
        """Return how many reviews sit in each season for a licence."""
        tally: dict[Season, int] = dict.fromkeys(Season, 0)
        for month, count in self.counts_by_month(serial).items():
            tally[month.season()] += count
        return tally

    def from_capture(self, digest: str) -> tuple[Review, ...]:
        """Return the reviews read out of one capture."""
        rows = self.db.conn.execute(
            f"{SELECT} WHERE capture_digest = ? ORDER BY review_key", (digest,)
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def remove_for_licence(self, serial: int) -> int:
        """Drop every review held against a licence and return how many went."""
        held = self.count_for(serial)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM review WHERE licence_serial = ?", (serial,))
        return held
