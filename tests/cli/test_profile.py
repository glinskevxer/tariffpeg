"""A case file citing seaboard/v3 has to be answerable without the file it came from."""

from __future__ import annotations

from pathlib import Path

from tests.cli.conftest import Run
from tests.cli.harvest_setup import REF, stock, write_bundle, write_profiles


def test_a_profile_file_is_registered_into_the_store(run: Run, tmp_path: Path) -> None:
    stock(run)
    result = run("profile", "register", str(write_profiles(tmp_path)), "--on", "2026-01-05")
    assert result.exit_code == 0
    assert "1 profiles registered on 2026-01-05" in result.output
    assert "seaboard" in run("profile", "list").output


def test_a_profile_for_a_channel_nobody_registered_is_refused(run: Run, tmp_path: Path) -> None:
    run("db", "migrate")
    result = run("profile", "register", str(write_profiles(tmp_path)))
    assert result.exit_code == 2
    assert "not on the register" in result.output


def test_registering_a_channel_the_file_does_not_carry_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    result = run("profile", "register", str(write_profiles(tmp_path)), "--channel", "quayside")
    assert result.exit_code == 2
    assert "nothing to register here" in result.output


def test_the_same_version_twice_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    profiles = write_profiles(tmp_path)
    run("profile", "register", str(profiles))
    assert run("profile", "register", str(profiles)).exit_code == 4


def test_a_store_with_no_profiles_says_so(run: Run) -> None:
    stock(run)
    assert "no profiles are registered" in run("profile", "list").output


def test_a_profile_shows_every_field_it_reads(run: Run, tmp_path: Path) -> None:
    stock(run)
    run("profile", "register", str(write_profiles(tmp_path)))
    result = run("profile", "show", "seaboard")
    assert result.exit_code == 0
    assert "seaboard/v1" in result.output
    assert "one review sits at article.review" in result.output
    assert "channel_review_id" in result.output
    assert "state live" in result.output


def test_showing_a_channel_with_no_live_version_is_refused(run: Run) -> None:
    stock(run)
    result = run("profile", "show", "seaboard")
    assert result.exit_code == 2
    assert "no version is live" in result.output


def test_a_harvest_reads_with_the_profile_in_the_store(run: Run, tmp_path: Path) -> None:
    stock(run)
    run("profile", "register", str(write_profiles(tmp_path)))
    result = run("harvest", "run", "--bundle", str(write_bundle(tmp_path)), "--on", "2025-09-15")
    assert result.exit_code == 0
    assert "3 reviews added" in result.output
    assert "seaboard:91188" in run("review", "list", "--licence", REF).output


def test_a_harvest_with_no_profile_anywhere_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    result = run("harvest", "run", "--bundle", str(write_bundle(tmp_path)))
    assert result.exit_code == 2
    assert "no profile is registered" in result.output


def test_a_named_file_still_wins_over_the_store(run: Run, tmp_path: Path) -> None:
    stock(run)
    run("profile", "register", str(write_profiles(tmp_path)))
    result = run(
        "harvest",
        "run",
        "--profiles",
        str(write_profiles(tmp_path)),
        "--bundle",
        str(write_bundle(tmp_path)),
        "--on",
        "2025-09-15",
    )
    assert result.exit_code == 0
    assert "3 reviews added" in result.output


def test_the_retired_versions_can_be_asked_for(run: Run, tmp_path: Path) -> None:
    stock(run)
    profiles = write_profiles(tmp_path)
    run("profile", "register", str(profiles), "--on", "2026-01-05")
    second = tmp_path / "profiles-2.toml"
    second.write_text(
        profiles.read_text(encoding="utf-8").replace("version = 1", "version = 2"), encoding="utf-8"
    )
    run("profile", "register", str(second), "--on", "2026-06-01")
    every = run("profile", "list", "--all")
    assert "retired 2026-06-01" in every.output
    assert every.output.count("seaboard") == 2
    assert "retired" not in run("profile", "list").output
