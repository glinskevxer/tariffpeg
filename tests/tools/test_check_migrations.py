"""A migration that has run somewhere cannot be edited."""

from __future__ import annotations

from pathlib import Path

import pytest

from tariffpeg.store.migrations import MIGRATIONS, Migration
from tariffpeg.tools import check_migrations

ONE = Migration(1, "register", ("CREATE TABLE a (n INTEGER)",))
TWO = Migration(2, "evidence", ("CREATE TABLE b (n INTEGER)",))


def plant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, migrations: tuple[Migration, ...]
) -> Path:
    target = tmp_path / "migrations.lock"
    monkeypatch.setattr(check_migrations, "MIGRATIONS", migrations)
    monkeypatch.setattr(check_migrations, "lock_path", lambda: target)
    return target


def test_the_real_migrations_match_the_lock_file() -> None:
    assert check_migrations.problems() == []


def test_the_lock_file_beside_the_code_lists_every_migration() -> None:
    lines = check_migrations.lock_path().read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(MIGRATIONS)
    assert lines[0].startswith("001 register ")


def test_a_written_lock_file_makes_the_check_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (ONE, TWO))
    check_migrations.write()
    assert check_migrations.problems() == []


def test_a_missing_lock_file_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plant(monkeypatch, tmp_path, (ONE,))
    found = check_migrations.problems()
    assert found == ["there is no migrations.lock, run this check with --write to make one"]


def test_a_migration_that_has_changed_since_the_lock_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (ONE,))
    check_migrations.write()
    edited = Migration(1, "register", ("CREATE TABLE a (n TEXT)",))
    monkeypatch.setattr(check_migrations, "MIGRATIONS", (edited,))
    found = check_migrations.problems()
    assert found == ["migration 1 has changed since migrations.lock was written"]


def test_a_migration_renamed_since_the_lock_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (ONE,))
    check_migrations.write()
    monkeypatch.setattr(check_migrations, "MIGRATIONS", (Migration(1, "renamed", ONE.statements),))
    assert any("has changed since" in problem for problem in check_migrations.problems())


def test_a_new_migration_that_is_not_locked_yet_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (ONE,))
    check_migrations.write()
    monkeypatch.setattr(check_migrations, "MIGRATIONS", (ONE, TWO))
    found = check_migrations.problems()
    assert found == ["migration 2 is not in migrations.lock"]


def test_a_migration_the_lock_carries_and_the_code_does_not_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (ONE, TWO))
    check_migrations.write()
    monkeypatch.setattr(check_migrations, "MIGRATIONS", (ONE,))
    found = check_migrations.problems()
    assert found == ["migrations.lock carries migration 2, which the code does not"]


def test_a_gap_in_the_numbering_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (ONE, Migration(3, "evidence", ONE.statements)))
    check_migrations.write()
    assert any("not one upwards" in problem for problem in check_migrations.problems())


def test_a_name_that_is_not_a_slug_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (Migration(1, "The Register", ONE.statements),))
    check_migrations.write()
    assert any("not a slug" in problem for problem in check_migrations.problems())


def test_a_name_used_twice_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plant(monkeypatch, tmp_path, (ONE, Migration(2, "register", TWO.statements)))
    check_migrations.write()
    assert any("reuses the name" in problem for problem in check_migrations.problems())


def test_a_migration_that_runs_nothing_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (Migration(1, "register", ()),))
    check_migrations.write()
    assert any("runs nothing" in problem for problem in check_migrations.problems())


def test_a_statement_ending_in_a_semicolon_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (Migration(1, "register", ("CREATE TABLE a (n INTEGER);",)),))
    check_migrations.write()
    assert any("ending in a semicolon" in problem for problem in check_migrations.problems())


def test_writing_the_lock_from_the_command_line_exits_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (ONE,))
    monkeypatch.setattr("sys.argv", ["check_migrations", "--write"])
    assert check_migrations.main() == 0
    assert check_migrations.lock_path().exists()


def test_the_check_exits_nothing_on_a_clean_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["check_migrations"])
    assert check_migrations.main() == 0


def test_the_check_exits_one_when_it_finds_something(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plant(monkeypatch, tmp_path, (ONE,))
    monkeypatch.setattr("sys.argv", ["check_migrations"])
    assert check_migrations.main() == 1
