"""Every release problem this package has had was a seam between two tested layers."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg import service
from tariffpeg.claims.pack import PACK
from tariffpeg.clock import FixedClock
from tariffpeg.fetch.replay import ReplayTransport
from tariffpeg.harvest.budget import Budget
from tariffpeg.harvest.plan import Plan, Stop
from tariffpeg.model.determination import Determination
from tariffpeg.model.outcome import Disposition
from tariffpeg.report.movement import Movement, Reconciliation
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


def test_the_run_minutes_the_month_and_drafts_the_letter(ready: Database) -> None:
    try:
        lines = smoke.run_once(ready)
    finally:
        ready.close()
    assert "minuted as desk enquiry by R Bosustow" in lines
    assert any(line.startswith("letter drafted as a desk enquiry") for line in lines)


def test_the_run_sees_the_evidence_move_away_from_the_minute(ready: Database) -> None:
    try:
        lines = smoke.run_once(ready)
    finally:
        ready.close()
    assert "the ledger reads stepped back against the evidence now" in lines


def test_the_run_costs_a_further_harvest_against_the_channels(ready: Database) -> None:
    try:
        lines = smoke.run_once(ready)
    finally:
        ready.close()
    assert any("a further harvest would ask for" in line for line in lines)


def test_the_run_notices_a_month_that_minutes_itself_twice(
    ready: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def always_writes(*args: object, **kwargs: object) -> tuple[object, ...]:
        calls.append(1)
        return ("a minute",)

    monkeypatch.setattr(service, "minute", always_writes)
    try:
        with pytest.raises(AssertionError, match="second minute"):
            smoke.run_once(ready)
    finally:
        ready.close()


def test_the_run_notices_a_reconciliation_that_will_not_settle(
    ready: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    taken = Determination(
        licence_serial=4021,
        decided_at=smoke.AT,
        disposition=Disposition.DESK_ENQUIRY,
        score=3.5,
        access_score=0.0,
        capped=False,
        pack_version=PACK.version,
        minuted_at=smoke.STARTED,
        officer="R Bosustow",
    )
    unsettled = Reconciliation((Movement(4021, taken, Disposition.URGENT, PACK.version),))
    monkeypatch.setattr(service, "reconciliation", lambda *a, **k: unsettled)
    try:
        with pytest.raises(AssertionError, match="did not reconcile"):
            smoke.run_once(ready)
    finally:
        ready.close()


def test_the_run_notices_a_budget_that_costs_a_plan_at_nothing(
    ready: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    stop = Stop(4021, "seaboard", "https://seaboard.example/p", 1, 4, "short")
    monkeypatch.setattr(service, "plan", lambda *a, **k: Plan((stop,)))
    monkeypatch.setattr(service, "budget", lambda *a, **k: Budget())
    try:
        with pytest.raises(AssertionError, match="costed nothing"):
            smoke.count_the_cost(ready)
    finally:
        ready.close()
