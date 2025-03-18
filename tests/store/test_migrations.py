"""A store built somewhere else says so rather than being migrated on top of."""

from __future__ import annotations

import pytest

from tariffpeg.clock import FixedClock
from tariffpeg.errors import Conflict
from tariffpeg.store.db import Database
from tariffpeg.store.migrations import (
    MIGRATIONS,
    Migration,
    applied,
    applied_at,
    current_version,
    drift,
    migrate,
    pending,
)


def test_the_migrations_are_numbered_from_one_with_no_gaps() -> None:
    numbers = [m.number for m in MIGRATIONS]
    assert numbers == list(range(1, len(MIGRATIONS) + 1))


def test_every_migration_has_a_name_and_at_least_one_statement() -> None:
    for migration in MIGRATIONS:
        assert migration.name
        assert migration.statements


def test_a_digest_depends_on_the_statements_and_not_on_their_layout() -> None:
    one = Migration(1, "x", ("CREATE TABLE a (n INTEGER)",))
    same = Migration(1, "x", ("  CREATE TABLE a (n INTEGER)  ",))
    other = Migration(1, "x", ("CREATE TABLE b (n INTEGER)",))
    assert one.digest == same.digest
    assert one.digest != other.digest


def test_a_fresh_store_has_everything_pending_and_nothing_applied() -> None:
    with Database() as store:
        assert current_version(store) == 0
        assert pending(store) == MIGRATIONS
        assert applied(store) == {}


def test_migrating_runs_everything_once_and_then_nothing(clock: FixedClock) -> None:
    with Database() as store:
        ran = migrate(store, clock)
        assert ran == tuple(m.number for m in MIGRATIONS)
        assert migrate(store, clock) == ()
        assert pending(store) == ()
        assert current_version(store) == len(MIGRATIONS)


def test_the_register_tables_are_there_after_the_first_migration(db: Database) -> None:
    for table in ("licence", "licence_particular", "channel"):
        assert table in db.table_names()


def test_the_bookkeeping_records_the_name_and_the_digest(db: Database) -> None:
    record = applied(db)
    for migration in MIGRATIONS:
        name, digest = record[migration.number]
        assert name == migration.name
        assert digest == migration.digest


def test_the_time_a_migration_ran_is_kept(db: Database, clock: FixedClock) -> None:
    assert applied_at(db, 1) == clock.now()
    assert applied_at(db, 999) is None


def test_a_healthy_store_reports_no_drift(db: Database) -> None:
    assert drift(db) == ()


def test_a_migration_that_ran_with_different_statements_is_reported(db: Database) -> None:
    db.conn.execute("UPDATE schema_migration SET digest = 'deadbeefdeadbeef' WHERE number = 1")
    problems = drift(db)
    assert len(problems) == 1
    assert "different statements" in problems[0]


def test_a_migration_from_the_future_is_reported(db: Database, clock: FixedClock) -> None:
    db.conn.execute(
        "INSERT INTO schema_migration (number, name, digest, applied_at) VALUES (?, ?, ?, ?)",
        (99, "something-later", "abc123", "2027-01-01T00:00:00Z"),
    )
    problems = drift(db)
    assert any("not one this version knows about" in problem for problem in problems)


def test_migrating_a_drifted_store_refuses_rather_than_stacking_on_top(
    db: Database, clock: FixedClock
) -> None:
    db.conn.execute("UPDATE schema_migration SET digest = 'deadbeefdeadbeef' WHERE number = 1")
    with pytest.raises(Conflict, match="different statements"):
        migrate(db, clock)


def test_a_store_on_disk_keeps_its_migrations_across_a_reopen(
    file_db: Database, clock: FixedClock
) -> None:
    path = file_db.path
    file_db.close()
    with Database(path) as reopened:
        assert current_version(reopened) == len(MIGRATIONS)
        assert migrate(reopened, clock) == ()
