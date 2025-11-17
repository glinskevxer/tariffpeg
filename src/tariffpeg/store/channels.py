"""Reading and writing the channel register.

The fetch policy is flattened into columns rather than kept as a blob. An
inspector asked once why a harvest had stopped at four hundred requests, and the
answer has to be a column somebody can look at, not a field inside a serialised
object.
"""

from __future__ import annotations

import sqlite3

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.channel import Channel, CourtesyWindow, FetchPolicy, SyndicationClass
from tariffpeg.store.db import Database

COLUMNS = (
    "slug",
    "name",
    "base_url",
    "syndication",
    "locale",
    "scale_slug",
    "user_agent",
    "crawl_delay_ms",
    "daily_request_ceiling",
    "window_open",
    "window_close",
    "max_pages",
)
"""The channel columns, in the order the table declares them."""


PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)
"""One question mark per column, for an insert."""

ASSIGNMENTS = ", ".join(f"{column} = ?" for column in COLUMNS[1:])
"""The columns an update writes, which is every one but the key."""


def hydrate(row: sqlite3.Row) -> Channel:
    """Build a channel out of a register row."""
    policy = FetchPolicy(
        user_agent=str(row["user_agent"]),
        crawl_delay_ms=int(row["crawl_delay_ms"]),
        daily_request_ceiling=int(row["daily_request_ceiling"]),
        window=CourtesyWindow(int(row["window_open"]), int(row["window_close"])),
        max_pages_per_property=int(row["max_pages"]),
    )
    return Channel(
        slug=str(row["slug"]),
        name=str(row["name"]),
        base_url=str(row["base_url"]),
        syndication=SyndicationClass(str(row["syndication"])),
        policy=policy,
        scale_slug=str(row["scale_slug"]),
        locale=str(row["locale"]),
    )


def flatten(channel: Channel) -> tuple[object, ...]:
    """Return the row values for a channel, in column order."""
    policy = channel.policy
    return (
        channel.slug,
        channel.name,
        channel.base_url,
        str(channel.syndication),
        channel.locale,
        channel.scale_slug,
        policy.user_agent,
        policy.crawl_delay_ms,
        policy.daily_request_ceiling,
        policy.window.open_hour,
        policy.window.close_hour,
        policy.max_pages_per_property,
    )


class ChannelStore:
    """The channel register."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def exists(self, slug: str) -> bool:
        """Return whether a channel slug is already registered."""
        return (
            self.db.conn.execute("SELECT 1 FROM channel WHERE slug = ?", (slug,)).fetchone()
            is not None
        )

    def add(self, channel: Channel) -> None:
        """Register a channel."""
        if self.exists(channel.slug):
            raise AlreadyExists("channel", channel.slug)
        with self.db.transaction() as conn:
            conn.execute(
                f"INSERT INTO channel ({', '.join(COLUMNS)}) VALUES ({PLACEHOLDERS})",
                flatten(channel),
            )

    def replace(self, channel: Channel) -> None:
        """Write agreed terms over the ones already registered."""
        if not self.exists(channel.slug):
            raise NotFound("channel", channel.slug)
        values = flatten(channel)
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE channel SET {ASSIGNMENTS} WHERE slug = ?",
                (*values[1:], channel.slug),
            )

    def get(self, slug: str) -> Channel:
        """Return a channel by slug, or refuse."""
        row = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM channel WHERE slug = ?", (slug,)
        ).fetchone()
        if row is None:
            raise NotFound("channel", slug)
        return hydrate(row)

    def all(self) -> tuple[Channel, ...]:
        """Return every registered channel, by slug."""
        rows = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM channel ORDER BY slug"
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def of_class(self, syndication: SyndicationClass) -> tuple[Channel, ...]:
        """Return the channels of one syndication class, by slug."""
        rows = self.db.conn.execute(
            f"SELECT {', '.join(COLUMNS)} FROM channel WHERE syndication = ? ORDER BY slug",
            (str(syndication),),
        ).fetchall()
        return tuple(hydrate(row) for row in rows)

    def slugs(self) -> tuple[str, ...]:
        """Return the registered slugs, in order."""
        rows = self.db.conn.execute("SELECT slug FROM channel ORDER BY slug").fetchall()
        return tuple(str(row["slug"]) for row in rows)

    def remove(self, slug: str) -> None:
        """Take a channel off the register."""
        if not self.exists(slug):
            raise NotFound("channel", slug)
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM channel WHERE slug = ?", (slug,))
