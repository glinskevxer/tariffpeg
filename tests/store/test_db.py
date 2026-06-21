"""The store opens the same way everywhere, and a half written transaction is not a thing."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tariffpeg.errors import Conflict
from tariffpeg.store.db import MEMORY, Database, connect


def test_foreign_keys_are_on_because_the_evidence_chain_depends_on_them() -> None:
    conn = connect(MEMORY)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_rows_come_back_addressable_by_column_name() -> None:
    conn = connect(MEMORY)
    try:
        row = conn.execute("SELECT 7 AS keys").fetchone()
        assert row["keys"] == 7
    finally:
        conn.close()


def test_a_store_on_disk_is_opened_in_write_ahead_mode(tmp_path: Path) -> None:
    conn = connect(tmp_path / "evidence.sqlite3")
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        conn.close()


def test_the_database_closes_itself_when_used_as_a_context_manager() -> None:
    with Database() as store:
        store.conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        store.conn.execute("SELECT 1")


def test_closing_the_store_twice_over_is_harmless() -> None:
    store = Database()
    store.close()
    store.close()


def test_a_transaction_commits_what_it_wrote(db: Database) -> None:
    with db.transaction() as conn:
        conn.execute("CREATE TABLE scratch (n INTEGER)")
        conn.execute("INSERT INTO scratch VALUES (1)")
    assert db.conn.execute("SELECT count(*) FROM scratch").fetchone()[0] == 1


def test_a_transaction_that_raises_leaves_nothing_behind(db: Database) -> None:
    db.conn.execute("CREATE TABLE scratch (n INTEGER)")
    with pytest.raises(RuntimeError), db.transaction() as conn:
        conn.execute("INSERT INTO scratch VALUES (1)")
        raise RuntimeError("something went wrong halfway")
    assert db.conn.execute("SELECT count(*) FROM scratch").fetchone()[0] == 0


def test_a_nested_transaction_joins_the_outer_one_rather_than_nesting(db: Database) -> None:
    db.conn.execute("CREATE TABLE scratch (n INTEGER)")
    with db.transaction() as outer:
        outer.execute("INSERT INTO scratch VALUES (1)")
        with db.transaction() as inner:
            inner.execute("INSERT INTO scratch VALUES (2)")
        assert db.in_transaction()
    assert not db.in_transaction()
    assert db.conn.execute("SELECT count(*) FROM scratch").fetchone()[0] == 2


def test_a_failure_inside_a_nested_block_rolls_the_outer_one_back(db: Database) -> None:
    db.conn.execute("CREATE TABLE scratch (n INTEGER)")
    with pytest.raises(RuntimeError), db.transaction() as outer:
        outer.execute("INSERT INTO scratch VALUES (1)")
        with db.transaction() as inner:
            inner.execute("INSERT INTO scratch VALUES (2)")
            raise RuntimeError("the inner block gave up")
    assert db.conn.execute("SELECT count(*) FROM scratch").fetchone()[0] == 0
    assert not db.in_transaction()


def test_a_writer_can_insist_it_was_called_inside_a_transaction(db: Database) -> None:
    with pytest.raises(Conflict, match="inside a transaction"):
        db.require_transaction("saving a licence")
    with db.transaction():
        db.require_transaction("saving a licence")


def test_the_table_listing_skips_sqlites_own(db: Database) -> None:
    names = db.table_names()
    assert "licence" in names
    assert "schema_migration" in names
    assert not [name for name in names if name.startswith("sqlite_")]
    assert list(names) == sorted(names)


def test_the_index_listing_reports_what_the_migrations_made(db: Database) -> None:
    assert "licence_locality" in db.index_names()
    assert not [name for name in db.index_names() if name.startswith("sqlite_")]


def test_a_healthy_store_reports_no_integrity_problems(db: Database) -> None:
    assert db.integrity_problems() == ()


def test_an_orphan_row_is_reported_by_the_integrity_check(db: Database) -> None:
    db.conn.execute("PRAGMA foreign_keys = OFF")
    db.conn.execute(
        "INSERT INTO licence_particular (serial, claim_key, kind, value) VALUES (?, ?, ?, ?)",
        (9999, "lift", "flag", 0),
    )
    problems = db.integrity_problems()
    assert any("licence_particular" in problem for problem in problems)


def test_the_path_is_remembered_so_an_error_can_name_the_file(tmp_path: Path) -> None:
    target = tmp_path / "evidence.sqlite3"
    with Database(target) as store:
        assert store.path == str(target)
    with Database() as memory_store:
        assert memory_store.path == MEMORY


def test_a_backup_is_a_working_store_with_the_same_rows(db: Database, tmp_path: Path) -> None:
    db.conn.execute("CREATE TABLE note (line TEXT)")
    db.conn.execute("INSERT INTO note (line) VALUES ('the roof leaks')")
    target = db.backup_to(tmp_path / "copies" / "evidence.sqlite3")
    assert target.exists()
    with Database(target) as copy:
        assert copy.integrity_problems() == ()
        rows = copy.conn.execute("SELECT line FROM note").fetchall()
    assert [row["line"] for row in rows] == ["the roof leaks"]


def test_a_backup_carries_writes_that_are_still_in_the_log(tmp_path: Path) -> None:
    with Database(tmp_path / "live.sqlite3") as store:
        store.conn.execute("CREATE TABLE note (line TEXT)")
        with store.transaction() as conn:
            conn.execute("INSERT INTO note (line) VALUES ('written under wal')")
        target = store.backup_to(tmp_path / "copy.sqlite3")
    with Database(target) as copy:
        assert copy.conn.execute("SELECT count(*) FROM note").fetchone()[0] == 1


def test_backing_up_does_not_disturb_the_store_it_copied(db: Database, tmp_path: Path) -> None:
    db.conn.execute("CREATE TABLE note (line TEXT)")
    db.backup_to(tmp_path / "copy.sqlite3")
    db.conn.execute("INSERT INTO note (line) VALUES ('still writable')")
    assert db.conn.execute("SELECT count(*) FROM note").fetchone()[0] == 1


def test_a_store_grows_as_rows_are_written_into_it() -> None:
    with Database() as store:
        empty = store.byte_size()
        store.conn.execute("CREATE TABLE note (line TEXT)")
        store.conn.executemany(
            "INSERT INTO note (line) VALUES (?)", [("x" * 400,) for _ in range(200)]
        )
        assert store.byte_size() > empty


def test_the_size_is_the_pages_and_not_what_the_log_beside_it_weighs(tmp_path: Path) -> None:
    target = tmp_path / "logged.sqlite3"
    with Database(target) as store:
        store.conn.execute("CREATE TABLE note (line TEXT)")
        with store.transaction() as conn:
            conn.executemany(
                "INSERT INTO note (line) VALUES (?)", [("x" * 400,) for _ in range(200)]
            )
        assert store.byte_size() > target.stat().st_size


def test_reclaiming_gives_back_the_pages_a_delete_freed(tmp_path: Path) -> None:
    with Database(tmp_path / "fat.sqlite3") as store:
        store.conn.execute("CREATE TABLE note (line TEXT)")
        with store.transaction() as conn:
            conn.executemany(
                "INSERT INTO note (line) VALUES (?)",
                [("x" * 400,) for _ in range(400)],
            )
        with store.transaction() as conn:
            conn.execute("DELETE FROM note")
        assert store.reclaim() > 0


def test_reclaiming_a_store_with_nothing_to_give_back_frees_nothing(db: Database) -> None:
    assert db.reclaim() == 0
