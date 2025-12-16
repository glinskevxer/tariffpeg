"""A document that drifts from the code stops a build rather than misleading somebody."""

from __future__ import annotations

from pathlib import Path

import pytest

from tariffpeg.tools import document


@pytest.fixture(autouse=True)
def somewhere_else(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(document, "repo_root", lambda: tmp_path)


def test_a_document_carries_a_title_and_a_banner() -> None:
    text = document.render("build_x", "Rules", ["one line"])
    assert text.startswith("# Rules\n")
    assert "Written by build_x" in text
    assert text.endswith("one line\n")


def test_a_document_is_written_under_the_docs_directory(tmp_path: Path) -> None:
    target = document.write("rules.md", "# Rules\n")
    assert target == tmp_path / "docs" / "rules.md"
    assert target.read_text(encoding="utf-8") == "# Rules\n"


def test_a_document_nobody_has_written_reads_as_stale() -> None:
    assert document.stale("rules.md", "# Rules\n") == "rules.md has never been written"


def test_a_document_that_matches_the_code_is_not_stale() -> None:
    document.write("rules.md", "# Rules\n")
    assert document.stale("rules.md", "# Rules\n") == ""


def test_a_document_that_has_drifted_reads_as_stale() -> None:
    document.write("rules.md", "# Rules\n")
    problem = document.stale("rules.md", "# Rules\n\nsomething new\n")
    assert problem == "rules.md is not what the code would write"


def test_running_a_generator_writes_the_document() -> None:
    assert document.run("build_x", "rules.md", "# Rules\n", []) == 0
    assert document.document_path("rules.md").exists()


def test_checking_a_document_that_is_up_to_date_exits_nothing() -> None:
    document.run("build_x", "rules.md", "# Rules\n", [])
    assert document.run("build_x", "rules.md", "# Rules\n", ["--check"]) == 0


def test_checking_a_document_that_has_drifted_exits_one() -> None:
    document.run("build_x", "rules.md", "# Rules\n", [])
    assert document.run("build_x", "rules.md", "# Rules\n\nmore\n", ["--check"]) == 1


def test_checking_a_document_writes_nothing() -> None:
    document.run("build_x", "rules.md", "# Rules\n", ["--check"])
    assert not document.document_path("rules.md").exists()


def test_a_table_carries_a_heading_row_and_a_rule() -> None:
    lines = document.table(["a", "b"], [["1", "2"]])
    assert lines[0] == "| a | b |"
    assert lines[1] == "| --- | --- |"
    assert lines[2] == "| 1 | 2 |"


def test_a_cell_with_a_pipe_in_it_is_escaped() -> None:
    lines = document.table(["a"], [["one|two"]])
    assert lines[2] == r"| one\|two |"
