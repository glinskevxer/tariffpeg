"""Keeping the extraction profiles in the store as well as in a file.

The file is where a profile is written and argued over. The store is where the
version that actually read a page is kept, so that a case file citing
``seaboard/v3`` can be answered years later by somebody who no longer has the
file that version came out of.

A profile is never edited in the store. A change is a new version, and the old
one is retired with the day it stopped being used, because a review read by
version two has to keep meaning what version two meant.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections.abc import Sequence

from tariffpeg.errors import AlreadyExists, Conflict, NotFound
from tariffpeg.model.profile import FieldRule, Profile
from tariffpeg.store.db import Database

COLUMNS = (
    "channel",
    "version",
    "container",
    "next_page",
    "prefer_structured",
    "registered_on",
    "retired_on",
)
"""The profile columns, in the order the table declares them."""

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
"""One question mark per column, for an insert."""

FIELD_COLUMNS = (
    "channel",
    "version",
    "name",
    "source",
    "selector",
    "attribute",
    "key",
    "required",
    "position",
)
"""The field columns, in the order the table declares them."""

FIELD_PLACEHOLDERS = ", ".join("?" for _ in FIELD_COLUMNS)
"""One question mark per field column."""

SELECT = f"SELECT {', '.join(COLUMNS)} FROM profile"
FIELD_SELECT = f"SELECT {', '.join(FIELD_COLUMNS)} FROM profile_field"


def field_of(row: sqlite3.Row) -> FieldRule:
    """Build one field rule out of a row."""
    return FieldRule(
        name=str(row["name"]),
        source=str(row["source"]),
        selector=str(row["selector"]),
        attribute=str(row["attribute"]),
        key=str(row["key"]),
        required=bool(row["required"]),
    )


class ProfileStore:
    """The profiles the store has actually read pages with."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, channel: str, version: int) -> bool:
        """Return whether this version is already in the store."""
        row = self.db.conn.execute(
            "SELECT 1 FROM profile WHERE channel = ? AND version = ?", (channel, version)
        ).fetchone()
        return row is not None

    def register(self, profile: Profile, on: dt.date) -> None:
        """Put a version in the store, retiring whatever was live before it."""
        if self.exists(profile.channel, profile.version):
            raise AlreadyExists("profile", profile.key())
        live = self.live(profile.channel)
        if live is not None and live.version > profile.version:
            raise Conflict("profile", f"version {live.version} is live and is later than this one")
        with self.db.transaction() as conn:
            if live is not None:
                conn.execute(
                    "UPDATE profile SET retired_on = ? WHERE channel = ? AND version = ?",
                    (on.isoformat(), live.channel, live.version),
                )
            conn.execute(
                f"INSERT INTO profile ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})",
                (
                    profile.channel,
                    profile.version,
                    profile.container,
                    profile.next_page,
                    int(profile.prefer_structured),
                    on.isoformat(),
                    "",
                ),
            )
            for position, rule in enumerate(profile.fields):
                conn.execute(
                    f"INSERT INTO profile_field ({', '.join(FIELD_COLUMNS)})"
                    f" VALUES ({FIELD_PLACEHOLDERS})",
                    (
                        profile.channel,
                        profile.version,
                        rule.name,
                        rule.source,
                        rule.selector,
                        rule.attribute,
                        rule.key,
                        int(rule.required),
                        position,
                    ),
                )

    def _fields(self, channel: str, version: int) -> tuple[FieldRule, ...]:
        rows = self.db.conn.execute(
            f"{FIELD_SELECT} WHERE channel = ? AND version = ? ORDER BY position",
            (channel, version),
        ).fetchall()
        return tuple(field_of(row) for row in rows)

    def _hydrate(self, row: sqlite3.Row) -> Profile:
        channel, version = str(row["channel"]), int(row["version"])
        return Profile(
            channel=channel,
            version=version,
            container=str(row["container"]),
            fields=self._fields(channel, version),
            next_page=str(row["next_page"]),
            prefer_structured=bool(row["prefer_structured"]),
        )

    def get(self, channel: str, version: int) -> Profile:
        """Return one version, or refuse."""
        row = self.db.conn.execute(
            f"{SELECT} WHERE channel = ? AND version = ?", (channel, version)
        ).fetchone()
        if row is None:
            raise NotFound("profile", f"{channel}/v{version}")
        return self._hydrate(row)

    def live(self, channel: str) -> Profile | None:
        """Return the version currently reading a channel, or nothing."""
        row = self.db.conn.execute(
            f"{SELECT} WHERE channel = ? AND retired_on = '' ORDER BY version DESC LIMIT 1",
            (channel,),
        ).fetchone()
        return None if row is None else self._hydrate(row)

    def versions(self, channel: str) -> tuple[int, ...]:
        """Return every version held for a channel, oldest first."""
        rows = self.db.conn.execute(
            "SELECT version FROM profile WHERE channel = ? ORDER BY version", (channel,)
        ).fetchall()
        return tuple(int(row["version"]) for row in rows)

    def retired_on(self, channel: str, version: int) -> dt.date | None:
        """Return the day a version stopped being used, or nothing if it is live."""
        row = self.db.conn.execute(
            "SELECT retired_on FROM profile WHERE channel = ? AND version = ?", (channel, version)
        ).fetchone()
        if row is None:
            raise NotFound("profile", f"{channel}/v{version}")
        written = str(row["retired_on"])
        return dt.date.fromisoformat(written) if written else None

    def live_by_channel(self, channels: Sequence[str]) -> dict[str, Profile]:
        """Return the live profile for each channel that has one."""
        found: dict[str, Profile] = {}
        for slug in channels:
            profile = self.live(slug)
            if profile is not None:
                found[slug] = profile
        return found
