"""The whole thing, from a bundle on disk to a file an inspector is handed."""

from __future__ import annotations

from pathlib import Path

from tariffpeg.ids import format_licence_ref
from tests.cli.conftest import Run
from tests.cli.harvest_setup import REF, stock, write_bundle, write_profiles

GONE = format_licence_ref(9999)


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


def test_the_case_file_reads_as_headed_blocks(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("case", "show", REF, "--at", "2025-09")
    assert result.exit_code == 0
    for heading in ("IDENTITY", "WHY", "SAMPLE", "FINDINGS", "REMEDIATION", "VISIT"):
        assert heading in result.output
    assert "The Anchor Rooms" in result.output


def test_the_case_file_carries_the_capture_behind_every_quotation(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("case", "quotations", REF, "--at", "2025-09")
    assert result.exit_code == 0
    assert "sha256:" in result.output
    assert "no lift" in result.output


def test_a_licence_with_nothing_quoted_says_so(run: Run) -> None:
    stock(run)
    assert "nothing quoted against it" in run("case", "quotations", REF).output


def test_an_accepted_notice_shows_in_the_case_file(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
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
    run("remediation", "accept", REF, "lift", "RN-1")
    result = run("case", "show", REF, "--at", "2025-09")
    assert "RN-1 on lift" in result.output
    assert "predates an accepted remediation" in result.output


def test_the_case_file_is_written_out_as_files(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    out = tmp_path / "cases"
    result = run("case", "export", REF, "--to", str(out), "--at", "2025-09")
    assert result.exit_code == 0
    document = out / f"{REF}.txt"
    quotations = out / f"{REF}-quotations.csv"
    assert document.exists()
    assert quotations.exists()
    assert "FINDINGS" in document.read_text(encoding="utf-8")
    assert quotations.read_text(encoding="utf-8").splitlines()[0].startswith("particular,review")


def test_the_exported_quotations_carry_the_whole_digest(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    out = tmp_path / "cases"
    run("case", "export", REF, "--to", str(out), "--at", "2025-09")
    text = (out / f"{REF}-quotations.csv").read_text(encoding="utf-8")
    digests = [line.split(",")[5] for line in text.splitlines()[1:]]
    assert all(len(digest) == len("sha256:") + 64 for digest in digests)


def test_exporting_a_licence_nobody_registered_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    result = run("case", "export", GONE, "--to", str(tmp_path / "cases"))
    assert result.exit_code == 3
