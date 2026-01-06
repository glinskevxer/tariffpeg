"""Every release problem this package has had was a seam between two tested layers."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg import service
from tariffpeg.clock import FixedClock
from tariffpeg.fetch.replay import ReplayTransport
from tariffpeg.harvest.plan import Plan
from tariffpeg.store.db import Database
from tariffpeg.store.migrations import migrate
from tariffpeg.store.reviews import ReviewStore
from tariffpeg.tools import smoke


@pytest.fixture
def ready() -> Database:
    store = Database()
    migrate(store, FixedClock(smoke.STARTED))
    return store


def test_the_whole_pipeline_runs_end_to_end(ready: Database) -> None:
    try:
        lines = smoke.run_once(ready)
    finally:
        ready.close()
    assert lines[0] == "2 pages read, 4 reviews held"
    assert "disposition" in lines[2]


def test_the_reviews_land_with_the_captures_behind_them(ready: Database) -> None:
    try:
        smoke.run_once(ready)
        held = ReviewStore(ready).for_licence(4021)
        assert len(held) == len(smoke.REVIEWS)
        assert all(review.capture_digest.startswith("sha256:") for review in held)
    finally:
        ready.close()


def test_an_accepted_notice_lowers_the_score(ready: Database) -> None:
    try:
        lines = smoke.run_once(ready)
    finally:
        ready.close()
    before = float(lines[2].rsplit(" ", 1)[1])
    after = float(lines[3].rsplit(" ", 1)[1])
    assert after < before


def test_the_run_notices_when_the_pipeline_stops_giving_up_reviews(
    ready: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    thin = ReplayTransport()
    thin.add("https://seaboard.example/robots.txt", "User-agent: *\n")
    thin.add(
        "https://seaboard.example/property/4021/reviews",
        '<html><body><div id="reviews"></div></body></html>',
    )
    monkeypatch.setattr(smoke, "transport", lambda: thin)
    try:
        with pytest.raises(AssertionError, match="reviews stored, wanted"):
            smoke.run_once(ready)
    finally:
        ready.close()


def test_the_run_notices_when_the_plan_visits_nothing(
    ready: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "plan", lambda *a, **k: Plan())
    try:
        with pytest.raises(AssertionError, match="visited nothing"):
            smoke.run_once(ready)
    finally:
        ready.close()


def test_the_clock_steps_every_time_the_run_reads_it() -> None:
    clock = smoke.Ticking(dt.datetime(2026, 6, 1, tzinfo=dt.UTC))
    first = clock.now()
    second = clock.now()
    assert second == first + dt.timedelta(seconds=1)


def test_the_recording_answers_the_two_pages_and_the_robots_file() -> None:
    known = smoke.transport().known()
    assert len(known) == 3
    assert any(url.endswith("robots.txt") for url in known)
    assert any(url.endswith("page=2") for url in known)


def test_the_profile_reads_the_pages_the_recording_serves() -> None:
    assert smoke.profile().key() == "seaboard/v1"
    assert smoke.profile().next_page == "a.next"


def test_the_run_leaves_nothing_behind_and_exits_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["smoke", "--quiet"])
    assert smoke.main() == 0


def test_a_broken_pipeline_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(db: Database) -> list[str]:
        raise AssertionError("the lift was not found against the licence")

    monkeypatch.setattr(smoke, "run_once", refuse)
    monkeypatch.setattr("sys.argv", ["smoke"])
    assert smoke.main() == 1
