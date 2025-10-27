"""What the unit would do about each licence, on the command line."""

from __future__ import annotations

from pathlib import Path

from tests.cli.conftest import Run
from tests.cli.harvest_setup import REF, stock, write_bundle, write_profiles


def harvested(run: Run, tmp_path: Path) -> None:
    stock(run)
    run(
        "harvest",
        "run",
        "--profiles",
        str(write_profiles(tmp_path)),
        "--bundle",
        str(write_bundle(tmp_path)),
        "--on",
        "2025-09-15",
    )


def test_the_triage_list_says_what_would_happen(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-09")
    assert result.exit_code == 0
    assert "4021" in result.output
    assert "The Anchor Rooms" in result.output


def test_the_triage_list_can_be_narrowed_to_visits(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-09", "--needing-a-visit")
    assert "nothing needs doing" in result.output


def test_the_findings_behind_a_decision_are_printed(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "show", REF, "--at", "2025-09")
    assert result.exit_code == 0
    assert "the evidence scores" in result.output
    assert "lift" in result.output


def test_a_licence_with_nothing_against_it_says_so(run: Run) -> None:
    stock(run)
    result = run("triage", "show", REF, "--at", "2025-09")
    assert "nothing was found against the particulars" in result.output


def test_the_schedule_books_nothing_when_nothing_needs_a_visit(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "schedule", "--at", "2025-09", "--on", "2025-09-15")
    assert result.exit_code == 0
    assert "nothing needs a visit" in result.output


def test_the_triage_list_can_be_asked_for_as_comma_separated_text(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "2025-09", extra=["--csv"])
    assert result.output.splitlines()[0].startswith("licence,trading name,disposition")


def test_a_month_the_reader_does_not_know_is_refused(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("triage", "list", "--at", "last summer")
    assert result.exit_code == 2
    assert "not a shape this reader knows" in result.output
