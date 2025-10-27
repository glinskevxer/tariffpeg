"""The settings a run is using, on the command line."""

from __future__ import annotations

from pathlib import Path

from tests.cli.conftest import Run


def test_the_settings_in_force_are_printed(migrated: Run) -> None:
    result = migrated("config", "show")
    assert result.exit_code == 0
    assert "crawl_delay_ms" in result.output


def test_only_the_changed_settings_are_printed_when_that_is_asked_for(migrated: Run) -> None:
    result = migrated("config", "show", "--changed-only")
    assert "every setting is at its default" in result.output


def test_the_defaults_are_printed_on_their_own(migrated: Run) -> None:
    assert "inspectors" in migrated("config", "defaults").output


def test_a_settings_file_can_be_checked(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "tariffpeg.toml"
    target.write_text("[tariffpeg]\ncrawl_delay_ms = 5000\n", encoding="utf-8")
    result = migrated("config", "check", str(target))
    assert result.exit_code == 0
    assert "1 settings changed" in result.output
    assert "crawl_delay_ms = 5000" in result.output


def test_a_settings_file_with_a_typo_is_refused(migrated: Run, tmp_path: Path) -> None:
    target = tmp_path / "tariffpeg.toml"
    target.write_text("[tariffpeg]\ncrawl_delay_millis = 5000\n", encoding="utf-8")
    result = migrated("config", "check", str(target))
    assert result.exit_code == 2
    assert "no such key" in result.output
