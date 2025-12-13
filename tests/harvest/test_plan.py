"""One channel saying a thing is one channel, however long you read it for."""

from __future__ import annotations

import datetime as dt

from tariffpeg.harvest.plan import REVIEWS_A_PAGE, Plan, build, pages_for
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.listing import Listing
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.sample.coverage import Coverage, SeasonCoverage
from tests.conftest import AGENT

ON = dt.date(2026, 6, 1)
WINDOW = (StayMonth(2024, 7), StayMonth(2026, 6))


def listing(serial: int = 4021, channel: str = "seaboard", **over: object) -> Listing:
    base: dict[str, object] = {
        "licence_serial": serial,
        "channel": channel,
        "path": f"/property/{serial}/reviews",
        "property_ref": f"P-{serial}-{channel}",
        "confirmed_on": dt.date(2026, 1, 1),
    }
    base.update(over)
    return Listing(**base)  # type: ignore[arg-type]


def coverage(
    serial: int = 4021,
    peak_short: int = 4,
    channels_held: tuple[str, ...] = ("seaboard",),
    wanted_channels: int = 2,
) -> Coverage:
    return Coverage(
        serial=serial,
        seasons=(
            SeasonCoverage(Season.PEAK, 12, 12 - peak_short),
            SeasonCoverage(Season.SHOULDER, 8, 8),
            SeasonCoverage(Season.OFF, 5, 5),
        ),
        channels_held=channels_held,
        channels_wanted=wanted_channels,
        window=WINDOW,
        opinions=20,
    )


def test_a_licence_whose_sample_is_complete_is_not_visited(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    done = coverage(peak_short=0, channels_held=("seaboard", "quayside"))
    plan = build([anchor], {4021: [listing()]}, channels, {4021: done}, ON)
    assert plan.stops == ()
    assert plan.skipped == ("4021: the sample is complete",)


def test_a_licence_nobody_has_measured_is_not_visited(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    plan = build([anchor], {4021: [listing()]}, channels, {}, ON)
    assert plan.stops == ()
    assert "nothing has measured" in plan.skipped[0]


def test_a_licence_that_is_not_active_is_not_visited(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    lapsed = anchor.with_status(LicenceStatus.LAPSED)
    plan = build([lapsed], {4021: [listing()]}, channels, {4021: coverage()}, ON)
    assert plan.stops == ()
    assert plan.skipped == ("4021: the licence is lapsed",)


def test_a_short_licence_gets_a_stop_on_every_listed_channel(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    listings = {4021: [listing(), listing(channel="quayside")]}
    plan = build([anchor], listings, channels, {4021: coverage()}, ON)
    assert plan.channels() == ("quayside", "seaboard")
    assert len(plan.for_licence(4021)) == 2


def test_a_channel_that_has_given_nothing_yet_goes_first(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    listings = {4021: [listing(), listing(channel="quayside")]}
    plan = build([anchor], listings, channels, {4021: coverage()}, ON)
    assert plan.stops[0].channel == "quayside"
    assert plan.stops[0].priority == 0
    assert plan.stops[1].priority == 1


def test_the_reason_says_what_is_wanted(anchor: Licence, channels: dict[str, Channel]) -> None:
    listings = {4021: [listing(), listing(channel="quayside")]}
    plan = build([anchor], listings, channels, {4021: coverage()}, ON)
    assert "independent channels wanted" in plan.stops[0].reason
    assert "reviews short, worst in peak" in plan.stops[1].reason


def test_a_licence_short_on_reviews_but_not_on_channels_reads_them_all_equally(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    held = coverage(channels_held=("seaboard", "quayside"))
    listings = {4021: [listing(), listing(channel="quayside")]}
    plan = build([anchor], listings, channels, {4021: held}, ON)
    assert {stop.priority for stop in plan.stops} == {1}


def test_a_retired_listing_is_skipped_and_said(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    retired = listing().retired("the channel took the page down")
    plan = build([anchor], {4021: [retired]}, channels, {4021: coverage()}, ON)
    assert plan.stops == ()
    assert "the listing is retired" in plan.skipped[0]


def test_a_listing_nobody_has_confirmed_lately_is_skipped_and_said(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    old = listing(confirmed_on=dt.date(2020, 1, 1))
    plan = build([anchor], {4021: [old]}, channels, {4021: coverage()}, ON)
    assert plan.stops == ()
    assert "the listing needs checking" in plan.skipped[0]


def test_a_listing_on_a_channel_the_register_forgot_is_skipped(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    plan = build([anchor], {4021: [listing(channel="gone")]}, channels, {4021: coverage()}, ON)
    assert plan.stops == ()
    assert "no such channel" in plan.skipped[0]


def test_the_url_is_the_listing_path_on_the_channel_base(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    plan = build([anchor], {4021: [listing()]}, channels, {4021: coverage()}, ON)
    assert plan.stops[0].url == "https://seaboard.example/property/4021/reviews"


def test_the_page_count_follows_the_shortfall() -> None:
    channel = Channel(
        slug="seaboard",
        name="Seaboard",
        base_url="https://seaboard.example",
        syndication=SyndicationClass.PRIMARY,
        policy=FetchPolicy(AGENT, 1500, 400, max_pages_per_property=3),
    )
    assert pages_for(1, channel) == 1
    assert pages_for(REVIEWS_A_PAGE, channel) == 1
    assert pages_for(REVIEWS_A_PAGE + 1, channel) == 2
    assert pages_for(1000, channel) == 3


def test_the_plan_totals_the_pages_it_will_ask_for(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    listings = {4021: [listing(), listing(channel="quayside")]}
    plan = build([anchor], listings, channels, {4021: coverage()}, ON)
    assert plan.total_pages == sum(stop.pages for stop in plan.stops)
    assert plan.total_pages > 0


def test_the_plan_can_be_read_a_channel_at_a_time(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    listings = {4021: [listing(), listing(channel="quayside")]}
    plan = build([anchor], listings, channels, {4021: coverage()}, ON)
    assert len(plan.for_channel("seaboard")) == 1
    assert plan.for_channel("atlas") == ()


def test_the_plan_explains_itself_a_stop_at_a_time(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    plan = build([anchor], {4021: [listing()]}, channels, {4021: coverage()}, ON)
    lines = plan.explain()
    assert lines[0].startswith("4021 on seaboard:")
    assert "pages" in lines[0]


def test_an_empty_plan_explains_nothing_and_asks_for_nothing() -> None:
    plan = Plan()
    assert plan.explain() == ()
    assert plan.total_pages == 0
    assert plan.channels() == ()
