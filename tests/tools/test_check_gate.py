"""A tool that only runs where nobody is looking is the same as not having it."""

from __future__ import annotations

from pathlib import Path

import pytest

from tariffpeg.tools import check_gate

WORKFLOW = """
jobs:
  checks:
    steps:
      - run: python -m tariffpeg.tools.check_one
      - run: python -m tariffpeg.tools.build_one --check
      - run: python -m tariffpeg.tools.smoke
"""
SCRIPT = "for t in check_*.py build_*.py; do echo $t; done\n"


@pytest.fixture
def tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(WORKFLOW, encoding="utf-8")
    (tmp_path / "check.sh").write_text(SCRIPT, encoding="utf-8")
    monkeypatch.setattr(check_gate, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(check_gate, "tools_on_disk", lambda: ({"check_one"}, {"build_one"}))
    return tmp_path


def test_the_real_tree_runs_every_tool_everywhere() -> None:
    assert check_gate.problems() == []


def test_a_tree_that_lists_everything_reads_clean(tree: Path) -> None:
    assert check_gate.problems() == []


def test_a_tool_the_pipeline_never_runs_is_reported(
    tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        check_gate, "tools_on_disk", lambda: ({"check_one", "check_two"}, {"build_one"})
    )
    found = check_gate.problems()
    assert found == ["check_two is not run by .github/workflows/ci.yml"]


def test_a_generator_the_pipeline_never_checks_is_reported(
    tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        check_gate, "tools_on_disk", lambda: ({"check_one"}, {"build_one", "build_two"})
    )
    assert any("build_two is not run" in problem for problem in check_gate.problems())


def test_a_tool_the_pipeline_runs_that_is_not_in_the_tree_is_reported(
    tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_gate, "tools_on_disk", lambda: (set(), set()))
    found = check_gate.problems()
    assert any("which is not a tool in the tree" in problem for problem in found)


def test_a_pipeline_that_never_runs_the_smoke_run_is_reported(tree: Path) -> None:
    workflow = tree / ".github" / "workflows" / "ci.yml"
    workflow.write_text(WORKFLOW.replace("smoke", "nothing"), encoding="utf-8")
    assert any("never runs the smoke run" in problem for problem in check_gate.problems())


def test_a_script_that_lists_the_tools_by_hand_is_reported(tree: Path) -> None:
    (tree / "check.sh").write_text("python -m tariffpeg.tools.check_one\n", encoding="utf-8")
    found = check_gate.problems()
    assert any("does not pick up check_*.py by wildcard" in problem for problem in found)


def test_a_tree_with_no_script_is_reported(tree: Path) -> None:
    (tree / "check.sh").unlink()
    assert any("there is no check.sh" in problem for problem in check_gate.problems())


def test_a_tree_with_no_pipeline_is_reported(tree: Path) -> None:
    (tree / ".github" / "workflows" / "ci.yml").unlink()
    found = check_gate.problems()
    assert found[-1] == "there is no .github/workflows/ci.yml"


def test_the_tools_on_disk_are_read_off_the_directory() -> None:
    checks, builders = check_gate.tools_on_disk()
    assert "check_layers" in checks
    assert "build_rules" in builders
    assert "schema_dump" in builders


def test_the_check_exits_nothing_on_a_clean_tree() -> None:
    assert check_gate.main() == 0


def test_the_check_exits_one_when_it_finds_something(
    tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check_gate, "tools_on_disk", lambda: ({"check_missing"}, {"build_one"}))
    assert check_gate.main() == 1
