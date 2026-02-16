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


def test_the_month_falls_back_to_the_one_the_clock_is_in() -> None:
    import datetime as dt
    from pathlib import Path as _Path

    from tariffpeg.cli.context import Context
    from tariffpeg.cli.harvest import month_or_now
    from tariffpeg.clock import FixedClock
    from tariffpeg.model.period import StayMonth

    ctx = Context(
        database=_Path("x.sqlite3"), clock=FixedClock(dt.datetime(2025, 9, 4, tzinfo=dt.UTC))
    )
    assert month_or_now("", ctx) == StayMonth(2025, 9)
    assert month_or_now("2024-02", ctx) == StayMonth(2024, 2)


def test_reaching_the_network_because_nobody_said_not_to_is_refused() -> None:
    import pytest as _pytest

    from tariffpeg.cli.harvest import transport_for
    from tariffpeg.errors import Invalid

    with _pytest.raises(Invalid, match="--bundle to replay or --live"):
        transport_for(None, False)


def test_asking_for_both_a_bundle_and_the_network_is_refused(tmp_path: Path) -> None:
    import pytest as _pytest

    from tariffpeg.cli.harvest import transport_for
    from tariffpeg.errors import Invalid

    with _pytest.raises(Invalid, match="not both"):
        transport_for(tmp_path, True)


def test_a_bundle_gives_back_a_transport_that_answers_out_of_it(tmp_path: Path) -> None:
    from tariffpeg.cli.harvest import transport_for
    from tariffpeg.fetch.replay import ReplayTransport

    bundle = write_bundle(tmp_path)
    assert isinstance(transport_for(bundle, False), ReplayTransport)
