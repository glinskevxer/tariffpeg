"""The difference between a retention rule and an accident is looking first."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.ids import capture_digest
from tariffpeg.model.capture import Capture
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.db import Database
from tariffpeg.store.retention import plan, run

FETCHED = dt.datetime(2025, 7, 4, 22, 15, tzinfo=dt.UTC)
CUTOFF = dt.date(2026, 1, 1)


def keep(store: CaptureStore, body: bytes, at: dt.datetime = FETCHED) -> str:
    """Record a capture with its bytes and return the digest."""
    digest = capture_digest(body)
    store.record(
        Capture(
            digest=digest,
            channel="seaboard",
            url=f"https://seaboard.example/p/{digest[7:15]}",
            final_url=f"https://seaboard.example/p/{digest[7:15]}",
            status=200,
            fetched_at=at,
            byte_count=len(body),
            profile_key="seaboard/v1",
            licence_serial=4021,
        )
    )
    store.keep_body(digest, body, at)
    return digest


def test_a_store_with_nothing_in_it_drops_nothing(stocked: Database) -> None:
    found = plan(stocked, CUTOFF)
    assert found.count == 0
    assert found.bytes_freed == 0
    assert "0 page bodies would go" in found.lines()[0]


def test_an_old_body_nothing_is_using_is_dropped(stocked: Database) -> None:
    store = CaptureStore(stocked)
    digest = keep(store, b"<html>an old page</html>")
    found = plan(stocked, CUTOFF)
    assert found.dropping == (digest,)
    assert found.bytes_freed == len(b"<html>an old page</html>")


def test_a_recent_body_is_kept(stocked: Database) -> None:
    store = CaptureStore(stocked)
    digest = keep(store, b"<html>a recent page</html>", dt.datetime(2026, 6, 1, tzinfo=dt.UTC))
    found = plan(stocked, CUTOFF)
    assert found.dropping == ()
    assert found.kept_recent == (digest,)


def test_a_body_quoted_in_a_live_case_file_is_kept(stocked: Database) -> None:
    store = CaptureStore(stocked)
    digest = keep(store, b"<html>a quoted page</html>")
    found = plan(stocked, CUTOFF, in_use={digest})
    assert found.dropping == ()
    assert found.kept_in_use == (digest,)
    assert "quoted in a live case file" in found.lines()[1]


def test_a_body_on_the_cutoff_day_itself_is_kept(stocked: Database) -> None:
    store = CaptureStore(stocked)
    keep(store, b"<html>on the day</html>", dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    assert plan(stocked, CUTOFF).dropping == ()


def test_a_capture_with_no_body_kept_is_not_in_the_plan(stocked: Database) -> None:
    store = CaptureStore(stocked)
    store.record(
        Capture(
            digest="sha256:" + "e" * 64,
            channel="seaboard",
            url="https://seaboard.example/p/none",
            final_url="https://seaboard.example/p/none",
            status=200,
            fetched_at=FETCHED,
            byte_count=0,
            profile_key="seaboard/v1",
        )
    )
    assert plan(stocked, CUTOFF).count == 0


def test_running_a_plan_drops_what_it_named(stocked: Database) -> None:
    store = CaptureStore(stocked)
    digest = keep(store, b"<html>an old page</html>")
    found = plan(stocked, CUTOFF)
    assert run(stocked, found) == 1
    assert not store.has_body(digest)
    assert store.exists(digest)


def test_running_an_empty_plan_drops_nothing(stocked: Database) -> None:
    assert run(stocked, plan(stocked, CUTOFF)) == 0


def test_a_plan_naming_a_capture_that_has_gone_is_refused(stocked: Database) -> None:
    store = CaptureStore(stocked)
    digest = keep(store, b"<html>an old page</html>")
    found = plan(stocked, CUTOFF)
    stocked.conn.execute("DELETE FROM capture WHERE digest = ?", (digest,))
    with pytest.raises(Invalid, match="not here any more"):
        run(stocked, found)


def test_the_plan_reads_as_three_lines_somebody_can_check(stocked: Database) -> None:
    store = CaptureStore(stocked)
    keep(store, b"<html>old</html>")
    keep(store, b"<html>recent</html>", dt.datetime(2026, 6, 1, tzinfo=dt.UTC))
    lines = plan(stocked, CUTOFF).lines()
    assert len(lines) == 3
    assert "1 page bodies would go" in lines[0]
    assert "1 are too recent" in lines[2]


def test_a_plan_with_nothing_in_it_is_the_shape_it_says() -> None:
    from tariffpeg.store.retention import Prune

    empty = Prune((), 0, (), ())
    assert isinstance(empty, Prune)
    assert empty.count == 0
    assert empty.bytes_freed == 0
