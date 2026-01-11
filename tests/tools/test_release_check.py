"""A gate that quietly passes because its tool could not be imported is worse than none."""

from __future__ import annotations

from pathlib import Path

import pytest

from tariffpeg import __version__
from tariffpeg.tools import release_check


def test_every_gate_passes_on_the_tree_as_it_stands() -> None:
    assert release_check.problems() == []


def test_there_is_a_gate_for_every_check_and_every_document() -> None:
    names = {gate.name for gate in release_check.gates()}
    assert "check_layers" in names
    assert "build_rules" in names
    assert "smoke" in names
    assert "version" in names


def test_the_version_in_the_code_matches_the_packaging() -> None:
    assert release_check.version_agrees() == []


def test_a_version_the_packaging_does_not_carry_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "pyproject.toml").write_text('version = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(release_check, "repo_root", lambda: tmp_path)
    found = release_check.version_agrees()
    assert found == [f'pyproject.toml does not say version = "{__version__}"']


def test_the_changelog_says_something_about_this_version() -> None:
    assert release_check.changelog_mentions_this_version() == []


def test_a_changelog_that_is_not_there_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(release_check, "repo_root", lambda: tmp_path)
    assert release_check.changelog_mentions_this_version() == ["there is no CHANGELOG.md"]


def test_a_changelog_with_no_entry_for_this_version_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    monkeypatch.setattr(release_check, "repo_root", lambda: tmp_path)
    found = release_check.changelog_mentions_this_version()
    assert found == [f"CHANGELOG.md says nothing about {__version__}"]


def test_the_readme_points_at_every_generated_document() -> None:
    assert release_check.readme_points_at_the_documents() == []


def test_a_readme_that_misses_a_document_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "README.md").write_text("# tariffpeg\n\nschema.md\n", encoding="utf-8")
    monkeypatch.setattr(release_check, "repo_root", lambda: tmp_path)
    found = release_check.readme_points_at_the_documents()
    assert "README.md does not point at build_rules" in found
    assert not any("schema_dump" in problem for problem in found)


def test_a_readme_that_is_not_there_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(release_check, "repo_root", lambda: tmp_path)
    assert release_check.readme_points_at_the_documents() == ["there is no README.md"]


def test_a_tool_that_will_not_import_is_a_failure_rather_than_a_pass() -> None:
    found = release_check._run_tool("nothing_like_this")
    assert len(found) == 1
    assert "could not be imported" in found[0]


def test_a_tool_that_does_not_pass_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    from tariffpeg.tools import check_layers

    monkeypatch.setattr(check_layers, "main", lambda: 1)
    assert release_check._run_tool("check_layers") == ["check_layers did not pass"]


def test_the_verbose_run_says_what_each_gate_did(capsys: pytest.CaptureFixture[str]) -> None:
    release_check.problems(verbose=True)
    printed = capsys.readouterr().out
    assert "release_check: version passed" in printed
    assert "release_check: smoke passed" in printed


def test_the_check_exits_nothing_when_every_gate_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["release_check"])
    assert release_check.main() == 0
