"""Nothing reaches the network unless somebody asks it to."""

from __future__ import annotations

from pathlib import Path

from tests.cli.conftest import Run
from tests.cli.harvest_setup import REF, stock, write_bundle, write_profiles


def test_the_plan_says_where_the_harvest_would_go(run: Run) -> None:
    stock(run)
    result = run("harvest", "plan", "--at", "2025-09", "--on", "2025-09-15")
    assert result.exit_code == 0
    assert "seaboard" in result.output
    assert "4021" in result.output


def test_the_plan_can_say_what_it_left_out(run: Run) -> None:
    stock(run)
    run("licence", "status", REF, "lapsed")
    result = run("harvest", "plan", "--on", "2025-09-15", "--skipped")
    assert "the licence is lapsed" in result.output


def test_a_run_with_neither_a_bundle_nor_live_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    profiles = write_profiles(tmp_path)
    result = run("harvest", "run", "--profiles", str(profiles))
    assert result.exit_code == 2
    assert "--bundle to replay or --live" in result.output


def test_a_run_asking_for_both_a_bundle_and_live_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    profiles = write_profiles(tmp_path)
    bundle = write_bundle(tmp_path)
    result = run("harvest", "run", "--profiles", str(profiles), "--bundle", str(bundle), "--live")
    assert result.exit_code == 2
    assert "not both" in result.output


def test_a_run_against_a_bundle_stores_what_it_reads(run: Run, tmp_path: Path) -> None:
    stock(run)
    profiles = write_profiles(tmp_path)
    bundle = write_bundle(tmp_path)
    result = run(
        "harvest",
        "run",
        "--profiles",
        str(profiles),
        "--bundle",
        str(bundle),
        "--at",
        "2025-09",
        "--on",
        "2025-09-15",
    )
    assert result.exit_code == 0
    assert "3 reviews added" in result.output
    listed = run("review", "list", "--licence", REF)
    assert "seaboard:91188" in listed.output


def test_running_twice_adds_nothing_the_second_time(run: Run, tmp_path: Path) -> None:
    stock(run)
    profiles = write_profiles(tmp_path)
    bundle = write_bundle(tmp_path)
    args = (
        "harvest",
        "run",
        "--profiles",
        str(profiles),
        "--bundle",
        str(bundle),
        "--on",
        "2025-09-15",
    )
    run(*args)
    result = run(*args)
    assert "0 reviews added" in result.output


def test_a_profile_file_that_is_not_there_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    bundle = write_bundle(tmp_path)
    result = run(
        "harvest", "run", "--profiles", str(tmp_path / "nothing.toml"), "--bundle", str(bundle)
    )
    assert result.exit_code == 2
    assert "no profile file here" in result.output


def test_a_bundle_that_is_not_there_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    profiles = write_profiles(tmp_path)
    result = run("harvest", "run", "--profiles", str(profiles), "--bundle", str(tmp_path / "no"))
    assert result.exit_code == 2
    assert "an index of the pages" in result.output


def test_the_problems_can_be_asked_for(run: Run, tmp_path: Path) -> None:
    stock(run)
    profiles = write_profiles(tmp_path)
    bundle = write_bundle(tmp_path)
    result = run(
        "harvest",
        "run",
        "--profiles",
        str(profiles),
        "--bundle",
        str(bundle),
        "--on",
        "2025-09-15",
        "--problems",
    )
    assert result.exit_code == 0


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
