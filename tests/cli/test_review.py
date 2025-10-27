"""The reviews the unit holds, on the command line."""

from __future__ import annotations

from pathlib import Path

from tests.cli.conftest import Run
from tests.cli.harvest_setup import stock, write_bundle, write_profiles


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


def test_the_reviews_read_back_with_their_scores(run: Run, tmp_path: Path) -> None:
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
    result = run("review", "show", "seaboard:91188")
    assert result.exit_code == 0
    assert "8.4" in result.output
    assert "no lift" in result.output
    assert "capture sha256:" in result.output


def test_a_review_nobody_holds_is_refused(run: Run) -> None:
    stock(run)
    result = run("review", "show", "seaboard:99999")
    assert result.exit_code == 3


def test_reviews_can_be_read_a_season_at_a_time(run: Run, tmp_path: Path) -> None:
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
    peak = run("review", "list", "--season", "peak")
    assert "seaboard:91188" in peak.output
    assert "seaboard:91190" not in peak.output


def test_reviews_can_be_read_a_channel_at_a_time(run: Run, tmp_path: Path) -> None:
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
    assert "seaboard:91188" in run("review", "list", "--channel", "seaboard").output
    assert "seaboard:91188" not in run("review", "list", "--channel", "quayside").output
