"""How far the statutory sample has got, on the command line."""

from __future__ import annotations

from pathlib import Path

from tariffpeg.ids import format_licence_ref
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


def test_the_coverage_of_a_licence_is_printed(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("sample", "coverage", REF, "--at", "2025-09")
    assert result.exit_code == 0
    assert "The Anchor Rooms" in result.output
    assert "distinct opinions held" in result.output
    assert "peak" in result.output


def test_the_coverage_of_a_licence_nobody_registered_is_refused(run: Run) -> None:
    stock(run)

    assert run("sample", "coverage", format_licence_ref(9999)).exit_code == 3


def test_the_shortfall_lists_what_is_still_wanted(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    result = run("sample", "shortfall", "--at", "2025-09")
    assert result.exit_code == 0
    assert "4021" in result.output
    assert "reviews short" in result.output


def test_the_regime_explains_what_it_asks_of_a_licence(run: Run) -> None:
    stock(run)
    result = run("sample", "regime", REF)
    assert result.exit_code == 0
    assert "regime version 1" in result.output
    assert "band 3 multiplies by" in result.output
    assert "reviews in all" in result.output
