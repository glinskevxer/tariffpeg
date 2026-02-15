"""A bundle that claims to hold a page it does not have is worse than a short one."""

from __future__ import annotations

from pathlib import Path

from tariffpeg.fetch.bundle import INDEX, load
from tariffpeg.fetch.transport import Request
from tariffpeg.ids import format_licence_ref
from tests.cli.conftest import Run
from tests.cli.harvest_setup import REF, stock, write_bundle, write_profiles
from tests.conftest import AGENT

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


def test_the_pages_behind_a_licence_are_written_out(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    out = tmp_path / "exported"
    result = run("case", "bundle", REF, "--to", str(out))
    assert result.exit_code == 0
    assert (out / INDEX).exists()
    assert "wrote 1 pages" in result.output


def test_the_bundle_that_comes_out_can_be_read_back(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    out = tmp_path / "exported"
    run("case", "bundle", REF, "--to", str(out))
    transport = load(out)
    url = "https://seaboard.example/property/4021/reviews"
    assert url in transport.known()
    served = transport.get(Request(url, AGENT))
    assert served.status == 200
    assert "91188" in served.text()


def test_the_pages_written_out_hash_to_what_the_store_holds(
    run: Run, tmp_path: Path, store_path: Path
) -> None:
    from tariffpeg.store.captures import CaptureStore
    from tariffpeg.store.db import Database

    harvested(run, tmp_path)
    out = tmp_path / "exported"
    run("case", "bundle", REF, "--to", str(out))
    with Database(store_path) as db:
        held = CaptureStore(db).for_licence(4021)
        bodies = {CaptureStore(db).body_of(capture.digest) for capture in held}
    written = {path.read_bytes() for path in out.glob("*.html")}
    assert written == bodies


def test_a_harvest_that_ran_again_can_be_replayed_from_the_bundle(run: Run, tmp_path: Path) -> None:
    harvested(run, tmp_path)
    out = tmp_path / "exported"
    run("case", "bundle", REF, "--to", str(out))
    again = run(
        "harvest",
        "run",
        "--profiles",
        str(write_profiles(tmp_path)),
        "--bundle",
        str(out),
        "--on",
        "2025-09-20",
    )
    assert again.exit_code == 0
    assert "0 reviews added" in again.output


def test_a_licence_with_no_pages_kept_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    result = run("case", "bundle", REF, "--to", str(tmp_path / "exported"))
    assert result.exit_code == 2
    assert "no pages behind this licence" in result.output


def test_a_licence_nobody_registered_is_refused(run: Run, tmp_path: Path) -> None:
    stock(run)
    assert run("case", "bundle", GONE, "--to", str(tmp_path / "exported")).exit_code == 3
