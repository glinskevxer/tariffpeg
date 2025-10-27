"""The notices operators file, on the command line."""

from __future__ import annotations

from tariffpeg.ids import format_licence_ref
from tests.cli.conftest import Run
from tests.cli.harvest_setup import REF, stock

GONE = format_licence_ref(9999)


def test_a_notice_is_taken_on_file_but_not_accepted(run: Run) -> None:
    stock(run)
    result = run(
        "remediation",
        "file",
        REF,
        "lift",
        "--reference",
        "RN-2026-0118",
        "--filed",
        "2026-03-04",
        "--effective",
        "2026-01",
    )
    assert result.exit_code == 0
    assert "not yet accepted" in result.output
    listed = run("remediation", "list", REF)
    assert "RN-2026-0118" in listed.output
    assert "no" in listed.output


def test_a_notice_about_a_particular_nobody_registers_is_refused(run: Run) -> None:
    stock(run)
    result = run(
        "remediation",
        "file",
        REF,
        "sauna",
        "--reference",
        "RN-1",
        "--filed",
        "2026-03-04",
        "--effective",
        "2026-01",
    )
    assert result.exit_code == 2
    assert "no such particular" in result.output


def test_a_notice_that_reaches_back_too_far_is_refused(run: Run) -> None:
    stock(run)
    result = run(
        "remediation",
        "file",
        REF,
        "lift",
        "--reference",
        "RN-1",
        "--filed",
        "2026-03-04",
        "--effective",
        "2024-01",
    )
    assert result.exit_code == 2
    assert "reach back more than" in result.output


def test_a_notice_can_be_accepted_and_then_shows_as_accepted(run: Run) -> None:
    stock(run)
    run(
        "remediation",
        "file",
        REF,
        "lift",
        "--reference",
        "RN-1",
        "--filed",
        "2026-03-04",
        "--effective",
        "2026-01",
    )
    result = run("remediation", "accept", REF, "lift", "RN-1", "--note", "certificate seen")
    assert result.exit_code == 0
    assert "certificate seen" in run("remediation", "list", REF).output
    assert "RN-1" in run("remediation", "list", REF, "--accepted-only").output


def test_a_notice_can_be_refused_with_a_reason(run: Run) -> None:
    stock(run)
    run(
        "remediation",
        "file",
        REF,
        "lift",
        "--reference",
        "RN-1",
        "--filed",
        "2026-03-04",
        "--effective",
        "2026-01",
    )
    result = run("remediation", "refuse", REF, "lift", "RN-1", "--why", "no certificate")
    assert result.exit_code == 0
    assert "no certificate" in run("remediation", "list", REF).output
    assert "RN-1" not in run("remediation", "list", REF, "--accepted-only").output


def test_a_licence_with_no_notices_says_so(run: Run) -> None:
    stock(run)
    assert "no notices on file" in run("remediation", "list", REF).output


def test_a_notice_against_a_licence_nobody_registered_is_refused(run: Run) -> None:
    stock(run)
    result = run(
        "remediation",
        "file",
        GONE,
        "lift",
        "--reference",
        "RN-1",
        "--filed",
        "2026-03-04",
        "--effective",
        "2026-01",
    )
    assert result.exit_code == 3
