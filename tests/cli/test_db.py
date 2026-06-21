"""A run that stopped because a channel refused us reads differently from a typo."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from tariffpeg import __version__
from tariffpeg.cli.main import main
from tests.cli.conftest import Run


def test_the_version_of_the_package_is_printed() -> None:
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_the_help_lists_the_groups() -> None:
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "db" in result.output


def test_migrating_a_fresh_store_applies_everything(run: Run) -> None:
    result = run("db", "migrate")
    assert result.exit_code == 0
    assert result.output.startswith("applied 1")


def test_migrating_twice_says_there_was_nothing_to_do(migrated: Run) -> None:
    result = migrated("db", "migrate")
    assert result.exit_code == 0
    assert "already up to date" in result.output


def test_the_status_says_the_schema_version_and_what_is_held(migrated: Run) -> None:
    result = migrated("db", "status")
    assert result.exit_code == 0
    assert "schema version" in result.output
    assert "licences" in result.output
    assert "reviews" in result.output


def test_the_status_of_an_unmigrated_store_reads_as_version_nothing(run: Run) -> None:
    result = run("db", "status")
    assert "schema version 0" in result.output


def test_the_migrations_are_listed_with_their_state(migrated: Run) -> None:
    result = migrated("db", "migrations")
    assert result.exit_code == 0
    assert "applied" in result.output
    assert "register" in result.output


def test_a_healthy_store_verifies_against_itself(migrated: Run) -> None:
    result = migrated("db", "verify")
    assert result.exit_code == 0
    assert "verifies" in result.output


def test_a_store_built_somewhere_else_does_not_verify(migrated: Run, store_path: Path) -> None:
    import sqlite3

    conn = sqlite3.connect(store_path)
    try:
        conn.execute("UPDATE schema_migration SET digest = 'deadbeefdeadbeef' WHERE number = 1")
        conn.commit()
    finally:
        conn.close()
    result = migrated("db", "verify")
    assert result.exit_code == 5
    assert "different statements" in result.output


def test_a_prune_that_was_not_asked_to_run_drops_nothing(migrated: Run) -> None:
    result = migrated("db", "prune", "--before", "2026-01-01")
    assert result.exit_code == 0
    assert "0 page bodies would go" in result.output
    assert "say --run to do it" in result.output


def test_a_prune_that_was_asked_to_run_says_how_many_went(migrated: Run) -> None:
    result = migrated("db", "prune", "--before", "2026-01-01", "--run")
    assert result.exit_code == 0
    assert "0 page bodies dropped" in result.output


def test_the_status_says_how_many_pages_and_bytes_are_kept(migrated: Run) -> None:
    result = migrated("db", "status")
    assert "pages kept" in result.output
    assert "bytes kept" in result.output


def test_a_backup_lands_where_it_was_asked_to_and_verifies(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "away" / "evidence.sqlite3"
    result = migrated("db", "backup", str(target))
    assert result.exit_code == 0
    assert "it verifies" in result.output
    assert target.exists()


def test_a_backup_can_be_opened_as_a_store_in_its_own_right(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "evidence.sqlite3"
    migrated("db", "backup", str(target))
    result = CliRunner().invoke(main, ["--db", str(target), "db", "status"])
    assert result.exit_code == 0
    assert "licences" in result.output


def test_reclaiming_says_how_much_the_store_gave_back(migrated: Run) -> None:
    result = migrated("db", "reclaim")
    assert result.exit_code == 0
    assert "bytes reclaimed" in result.output
