"""A held request does not become a retry loop, it becomes a line in the log."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.clock import FixedClock
from tariffpeg.fetch.replay import ReplayTransport
from tariffpeg.harvest.plan import Plan, Stop
from tariffpeg.harvest.runner import Runner, RunReport, StopReport
from tariffpeg.harvest.session import Session
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.parse.drift import DriftState, DriftWatch
from tariffpeg.parse.profile import Profile
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.reviews import ReviewStore
from tests.conftest import AGENT, a_channel
from tests.harvest.conftest import REVIEWS, page
from tests.store.conftest import a_licence

PAGE_ONE = "https://seaboard.example/property/4021/reviews"
PAGE_TWO = "https://seaboard.example/property/4021/reviews?page=2"
ROBOTS = "https://seaboard.example/robots.txt"


@pytest.fixture
def stocked_for_harvest(db: Database) -> Database:
    ChannelStore(db).add(a_channel("seaboard"))
    LicenceStore(db).add(a_licence())
    return db


@pytest.fixture
def transport() -> ReplayTransport:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE_ONE, page(REVIEWS))
    return replay


def a_stop(pages: int = 1, url: str = PAGE_ONE) -> Stop:
    return Stop(4021, "seaboard", url, 1, pages, "short in peak")


def brisk_channel() -> Channel:
    """A channel whose agreed delay is short enough to read two pages in a run."""
    return Channel(
        slug="seaboard",
        name="Seaboard Stays",
        base_url="https://seaboard.example",
        syndication=SyndicationClass.PRIMARY,
        policy=FetchPolicy(AGENT, 250, 400),
    )


def runner(
    db: Database,
    transport: ReplayTransport,
    profile: Profile,
    clock: FixedClock,
    watch: DriftWatch | None = None,
    channel: Channel | None = None,
) -> Runner:
    return Runner(
        db,
        Session(transport),
        {"seaboard": channel if channel is not None else a_channel("seaboard")},
        {"seaboard": profile},
        clock,
        watch,
    )


def test_a_run_reads_a_page_and_stores_what_it_finds(
    stocked_for_harvest: Database,
    transport: ReplayTransport,
    seaboard_profile: Profile,
    clock: FixedClock,
) -> None:
    report = runner(stocked_for_harvest, transport, seaboard_profile, clock).run(Plan((a_stop(),)))
    assert report.pages_read == 1
    assert report.captures == 1
    assert report.reviews_new == 3
    assert ReviewStore(stocked_for_harvest).count_for(4021) == 3
    assert CaptureStore(stocked_for_harvest).count() == 1


def test_the_reviews_land_with_their_scores_on_the_unit_scale(
    stocked_for_harvest: Database,
    transport: ReplayTransport,
    seaboard_profile: Profile,
    clock: FixedClock,
) -> None:
    runner(stocked_for_harvest, transport, seaboard_profile, clock).run(Plan((a_stop(),)))
    held = ReviewStore(stocked_for_harvest).get("seaboard:91188")
    assert held.raw_score == "8.4"
    assert held.unit_points == 79
    assert str(held.stay) == "2025-07"


def test_running_the_same_plan_twice_adds_nothing_the_second_time(
    stocked_for_harvest: Database,
    transport: ReplayTransport,
    seaboard_profile: Profile,
    clock: FixedClock,
) -> None:
    built = runner(stocked_for_harvest, transport, seaboard_profile, clock)
    built.run(Plan((a_stop(),)))
    clock.advance(days=1)
    again = built.run(Plan((a_stop(),)))
    assert again.reviews_new == 0
    assert again.captures == 0
    assert again.pages_read == 1


def test_a_run_follows_the_link_to_the_next_page_while_it_has_budget(
    stocked_for_harvest: Database, seaboard_profile: Profile, clock: FixedClock
) -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE_ONE, page(REVIEWS[:2], PAGE_TWO))
    replay.add(PAGE_TWO, page(REVIEWS[2:]))
    moving = _MovingClock(clock.now())
    built = Runner(
        stocked_for_harvest,
        Session(replay),
        {"seaboard": brisk_channel()},
        {"seaboard": seaboard_profile},
        moving,
    )
    report = built.run(Plan((a_stop(pages=4),)))
    assert report.pages_read == 2
    assert report.reviews_new == 3
    assert "no further pages" in report.stops[0].stopped_because


class _MovingClock:
    """A clock that steps a second every time it is read."""

    def __init__(self, at: dt.datetime) -> None:
        self._at = at

    def now(self) -> dt.datetime:
        self._at = self._at + dt.timedelta(seconds=1)
        return self._at


def test_the_page_budget_stops_the_walk(
    stocked_for_harvest: Database, seaboard_profile: Profile, clock: FixedClock
) -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE_ONE, page(REVIEWS[:2], PAGE_TWO))
    replay.add(PAGE_TWO, page(REVIEWS[2:]))
    report = runner(stocked_for_harvest, replay, seaboard_profile, clock).run(Plan((a_stop(1),)))
    assert report.pages_read == 1
    assert "read every page" in report.stops[0].stopped_because


def test_a_held_request_stops_the_stop_and_says_why(
    stocked_for_harvest: Database,
    transport: ReplayTransport,
    seaboard_profile: Profile,
    clock: FixedClock,
) -> None:
    built = runner(stocked_for_harvest, transport, seaboard_profile, clock)
    built.run(Plan((a_stop(),)))
    again = built.run(Plan((a_stop(),)))
    assert again.pages_read == 0
    assert "crawl delay" in again.stops[0].stopped_because


def test_a_stop_on_a_channel_the_register_forgot_says_so(
    stocked_for_harvest: Database,
    transport: ReplayTransport,
    seaboard_profile: Profile,
    clock: FixedClock,
) -> None:
    built = runner(stocked_for_harvest, transport, seaboard_profile, clock)
    report = built.run(Plan((Stop(4021, "gone", PAGE_ONE, 1, 1, "x"),)))
    assert report.stops[0].stopped_because == "no such channel"


def test_a_stop_with_no_profile_says_so(
    stocked_for_harvest: Database, transport: ReplayTransport, clock: FixedClock
) -> None:
    built = Runner(
        stocked_for_harvest,
        Session(transport),
        {"seaboard": a_channel("seaboard")},
        {},
        clock,
    )
    report = built.run(Plan((a_stop(),)))
    assert report.stops[0].stopped_because == "no such profile"


def test_the_skipped_lines_from_the_plan_are_carried_into_the_report(
    stocked_for_harvest: Database,
    transport: ReplayTransport,
    seaboard_profile: Profile,
    clock: FixedClock,
) -> None:
    plan = Plan((), ("4021: the sample is complete",))
    report = runner(stocked_for_harvest, transport, seaboard_profile, clock).run(plan)
    assert report.skipped == ("4021: the sample is complete",)
    assert report.lines() == ()


def test_the_run_records_a_reading_for_the_drift_watch(
    stocked_for_harvest: Database,
    transport: ReplayTransport,
    seaboard_profile: Profile,
    clock: FixedClock,
) -> None:
    watch = DriftWatch()
    runner(stocked_for_harvest, transport, seaboard_profile, clock, watch).run(Plan((a_stop(),)))
    readings = watch.readings("seaboard/v1")
    assert len(readings) == 1
    assert readings[0].blocks_seen == 3
    assert watch.state("seaboard/v1") is DriftState.HEALTHY


def test_a_page_that_gives_up_nothing_still_records_a_reading(
    stocked_for_harvest: Database, seaboard_profile: Profile, clock: FixedClock
) -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE_ONE, "<html><body><p>no reviews yet</p></body></html>")
    watch = DriftWatch()
    report = runner(stocked_for_harvest, replay, seaboard_profile, clock, watch).run(
        Plan((a_stop(),))
    )
    assert report.reviews_new == 0
    assert watch.readings("seaboard/v1")[0].blocks_seen == 0


def test_a_review_that_will_not_normalise_is_reported_and_the_rest_go_in(
    stocked_for_harvest: Database, seaboard_profile: Profile, clock: FixedClock
) -> None:
    broken = (("91199", "Bad", "The lift was out all week and nobody said.", "99", "July 2025"),)
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE_ONE, page(REVIEWS + broken))
    report = runner(stocked_for_harvest, replay, seaboard_profile, clock).run(Plan((a_stop(),)))
    assert report.reviews_new == 3
    assert any("dial runs from" in problem for problem in report.problems())


def test_the_log_line_names_the_licence_the_channel_and_the_count() -> None:
    line = StopReport(4021, "seaboard", 2, 2, 20, 18, "read every page").line()
    assert line.startswith("4021 on seaboard: 2 pages, 18 new of 20 seen")


def test_a_report_with_no_stops_counts_nothing() -> None:
    report = RunReport(dt.datetime(2025, 7, 4, tzinfo=dt.UTC))
    assert report.pages_read == 0
    assert report.reviews_new == 0
    assert report.problems() == ()
