"""Numbered migrations, applied in order and recorded with a digest.

An evidence bundle can be years old by the time somebody opens it. The store
records not just which migrations ran but what they said, so a file built by a
version of this package that no longer exists still reports honestly whether it
matches the schema this version expects.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

from tariffpeg.clock import Clock, SystemClock, isoformat, parse_instant
from tariffpeg.errors import Conflict
from tariffpeg.store.db import Database

BOOKKEEPING = """
CREATE TABLE IF NOT EXISTS schema_migration (
    number     INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    digest     TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


@dataclass(frozen=True, slots=True)
class Migration:
    """One numbered step, and the statements it runs."""

    number: int
    name: str
    statements: tuple[str, ...]

    @property
    def digest(self) -> str:
        """Return the digest recorded against this migration when it ran."""
        joined = "\n".join(statement.strip() for statement in self.statements)
        return hashlib.sha256(joined.encode()).hexdigest()[:16]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        "register",
        (
            """
            CREATE TABLE licence (
                serial        INTEGER PRIMARY KEY,
                trading_name  TEXT NOT NULL,
                operator_name TEXT NOT NULL,
                locality      TEXT NOT NULL,
                period_start  TEXT NOT NULL,
                period_end    TEXT NOT NULL,
                closed_months TEXT NOT NULL,
                status        TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE licence_particular (
                serial     INTEGER NOT NULL REFERENCES licence(serial) ON DELETE CASCADE,
                claim_key  TEXT NOT NULL,
                kind       TEXT NOT NULL,
                value      INTEGER NOT NULL,
                PRIMARY KEY (serial, claim_key)
            )
            """,
            """
            CREATE TABLE channel (
                slug                  TEXT PRIMARY KEY,
                name                  TEXT NOT NULL,
                base_url              TEXT NOT NULL,
                syndication           TEXT NOT NULL,
                locale                TEXT NOT NULL,
                scale_slug            TEXT NOT NULL,
                user_agent            TEXT NOT NULL,
                crawl_delay_ms        INTEGER NOT NULL,
                daily_request_ceiling INTEGER NOT NULL,
                window_open           INTEGER NOT NULL,
                window_close          INTEGER NOT NULL,
                max_pages             INTEGER NOT NULL
            )
            """,
            "CREATE INDEX licence_locality ON licence(locality)",
            "CREATE INDEX licence_status ON licence(status)",
            "CREATE INDEX licence_particular_claim ON licence_particular(claim_key)",
        ),
    ),
    Migration(
        2,
        "evidence",
        (
            """
            CREATE TABLE capture (
                digest         TEXT PRIMARY KEY,
                channel        TEXT NOT NULL REFERENCES channel(slug),
                url            TEXT NOT NULL,
                final_url      TEXT NOT NULL,
                status         INTEGER NOT NULL,
                fetched_at     TEXT NOT NULL,
                byte_count     INTEGER NOT NULL,
                elapsed_ms     INTEGER NOT NULL,
                profile_key    TEXT NOT NULL,
                licence_serial INTEGER,
                etag           TEXT NOT NULL DEFAULT ''
            )
            """,
            """
            CREATE TABLE review (
                review_key        TEXT PRIMARY KEY,
                channel           TEXT NOT NULL REFERENCES channel(slug),
                channel_review_id TEXT NOT NULL,
                licence_serial    INTEGER NOT NULL REFERENCES licence(serial) ON DELETE CASCADE,
                stay_year         INTEGER NOT NULL,
                stay_month        INTEGER NOT NULL,
                unit_points       INTEGER NOT NULL,
                raw_score         TEXT NOT NULL,
                title             TEXT NOT NULL,
                body              TEXT NOT NULL,
                reviewer_initials TEXT NOT NULL,
                room_class        TEXT NOT NULL,
                language          TEXT NOT NULL,
                submitted         TEXT NOT NULL,
                operator_response TEXT NOT NULL,
                capture_digest    TEXT NOT NULL REFERENCES capture(digest),
                profile_key       TEXT NOT NULL,
                first_seen        TEXT NOT NULL
            )
            """,
            "CREATE INDEX capture_channel ON capture(channel, fetched_at)",
            "CREATE INDEX capture_licence ON capture(licence_serial)",
            "CREATE INDEX review_licence ON review(licence_serial, stay_year, stay_month)",
            "CREATE INDEX review_channel ON review(channel)",
            "CREATE INDEX review_capture ON review(capture_digest)",
        ),
    ),
    Migration(
        3,
        "listings",
        (
            """
            CREATE TABLE listing (
                licence_serial INTEGER NOT NULL REFERENCES licence(serial) ON DELETE CASCADE,
                channel        TEXT NOT NULL REFERENCES channel(slug),
                path           TEXT NOT NULL,
                property_ref   TEXT NOT NULL,
                confirmed_on   TEXT NOT NULL,
                active         INTEGER NOT NULL,
                note           TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (licence_serial, channel)
            )
            """,
            "CREATE INDEX listing_channel ON listing(channel, active)",
            "CREATE UNIQUE INDEX listing_property ON listing(channel, property_ref)",
        ),
    ),
    Migration(
        4,
        "remediation",
        (
            """
            CREATE TABLE remediation (
                licence_serial   INTEGER NOT NULL REFERENCES licence(serial) ON DELETE CASCADE,
                claim_key        TEXT NOT NULL,
                reference        TEXT NOT NULL,
                filed_on         TEXT NOT NULL,
                effective_year   INTEGER NOT NULL,
                effective_month  INTEGER NOT NULL,
                accepted         INTEGER NOT NULL,
                note             TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (licence_serial, claim_key, reference)
            )
            """,
            "CREATE INDEX remediation_licence ON remediation(licence_serial, accepted)",
        ),
    ),
    Migration(
        5,
        "bodies",
        (
            """
            CREATE TABLE capture_body (
                digest    TEXT PRIMARY KEY REFERENCES capture(digest) ON DELETE CASCADE,
                body      BLOB NOT NULL,
                stored_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX capture_body_stored ON capture_body(stored_at)",
        ),
    ),
)
"""Every migration this package knows about, in the order they run."""


def _ensure_bookkeeping(db: Database) -> None:
    db.conn.execute(BOOKKEEPING)


def applied(db: Database) -> dict[int, tuple[str, str]]:
    """Return the migrations the store says have run, by number."""
    _ensure_bookkeeping(db)
    rows = db.conn.execute(
        "SELECT number, name, digest FROM schema_migration ORDER BY number"
    ).fetchall()
    return {int(row["number"]): (str(row["name"]), str(row["digest"])) for row in rows}


def current_version(db: Database) -> int:
    """Return the highest migration number the store has applied."""
    record = applied(db)
    return max(record) if record else 0


def pending(db: Database) -> tuple[Migration, ...]:
    """Return the migrations that have not run yet, in order."""
    record = applied(db)
    return tuple(m for m in MIGRATIONS if m.number not in record)


def drift(db: Database) -> tuple[str, ...]:
    """Return what the store disagrees with this package about.

    A migration recorded under a digest this package does not recognise means
    the file was built somewhere else. That is worth saying out loud rather than
    quietly running the next migration on top of it.
    """
    known = {m.number: m for m in MIGRATIONS}
    problems: list[str] = []
    for number, (name, digest) in sorted(applied(db).items()):
        migration = known.get(number)
        if migration is None:
            problems.append(f"migration {number} ({name}) is not one this version knows about")
        elif migration.digest != digest:
            problems.append(f"migration {number} ({name}) ran with different statements")
    return tuple(problems)


def migrate(db: Database, clock: Clock | None = None) -> tuple[int, ...]:
    """Apply every pending migration and return the numbers that ran."""
    problems = drift(db)
    if problems:
        raise Conflict("migration", problems[0])
    at = isoformat((clock or SystemClock()).now())
    ran: list[int] = []
    for migration in pending(db):
        with db.transaction() as conn:
            for statement in migration.statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migration (number, name, digest, applied_at)"
                " VALUES (?, ?, ?, ?)",
                (migration.number, migration.name, migration.digest, at),
            )
        ran.append(migration.number)
    return tuple(ran)


def applied_at(db: Database, number: int) -> dt.datetime | None:
    """Return when a migration ran, or ``None`` if it has not."""
    row = db.conn.execute(
        "SELECT applied_at FROM schema_migration WHERE number = ?", (number,)
    ).fetchone()
    if row is None:
        return None
    return parse_instant(str(row["applied_at"]))
