"""A plan that asks a channel for more than the day allows is shortened, not refused."""

from __future__ import annotations

from tariffpeg.harvest.budget import Allowance, Budget, measure, spend_by_channel, trim
from tariffpeg.harvest.plan import Plan, Stop
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass

AGENT = "tariffpeg-harvester (standards@example-authority.test)"


def channel(slug: str, ceiling: int) -> Channel:
    return Channel(
        slug=slug,
        name=slug.title(),
        base_url=f"https://{slug}.example",
        syndication=SyndicationClass.PRIMARY,
        policy=FetchPolicy(AGENT, 1500, ceiling),
    )


def stop(serial: int, slug: str, pages: int, priority: int = 1) -> Stop:
    return Stop(serial, slug, f"https://{slug}.example/p/{serial}", priority, pages, "short")


def test_an_allowance_that_fits_says_what_the_day_has_left() -> None:
    allowance = Allowance("seaboard", 100, 40, 20)
    assert allowance.remaining == 60
    assert allowance.granted == 20
    assert not allowance.over
    assert "20 of 60 left today" in allowance.line()


def test_an_allowance_asked_for_too_much_says_what_waits_for_tomorrow() -> None:
    allowance = Allowance("seaboard", 100, 90, 30)
    assert allowance.granted == 10
    assert allowance.refused == 20
    assert allowance.over
    assert "20 wait for tomorrow" in allowance.line()


def test_a_channel_that_has_had_its_whole_day_is_exhausted() -> None:
    allowance = Allowance("seaboard", 40, 40, 5)
    assert allowance.exhausted
    assert allowance.granted == 0


def test_a_channel_read_past_its_ceiling_still_has_nothing_left() -> None:
    assert Allowance("seaboard", 40, 55, 5).remaining == 0


def test_the_budget_adds_the_pages_up_per_channel() -> None:
    plan = Plan((stop(1, "seaboard", 4), stop(2, "seaboard", 3), stop(3, "quayside", 2)))
    found = measure(
        plan, {"seaboard": channel("seaboard", 100), "quayside": channel("quayside", 100)}, {}
    )
    assert [allowance.channel for allowance in found.allowances] == ["quayside", "seaboard"]
    assert found.for_channel("seaboard") is not None
    assert found.wanted == 9


def test_a_channel_the_register_does_not_carry_is_left_out_of_the_budget() -> None:
    plan = Plan((stop(1, "seaboard", 4), stop(2, "gone", 3)))
    found = measure(plan, {"seaboard": channel("seaboard", 100)}, {})
    assert [allowance.channel for allowance in found.allowances] == ["seaboard"]
    assert found.for_channel("gone") is None


def test_a_budget_that_fits_says_so() -> None:
    plan = Plan((stop(1, "seaboard", 4),))
    found = measure(plan, {"seaboard": channel("seaboard", 100)}, {"seaboard": 10})
    assert found.fits
    assert found.over_ceiling() == ()
    assert found.granted == 4


def test_a_budget_that_does_not_fit_names_the_channel() -> None:
    plan = Plan((stop(1, "seaboard", 40),))
    found = measure(plan, {"seaboard": channel("seaboard", 30)}, {"seaboard": 25})
    assert not found.fits
    assert found.over_ceiling() == ("seaboard",)
    assert found.granted == 5


def test_a_plan_inside_its_budget_is_left_alone() -> None:
    plan = Plan((stop(1, "seaboard", 4),))
    found = measure(plan, {"seaboard": channel("seaboard", 100)}, {})
    assert trim(plan, found).stops == plan.stops


def test_a_stop_that_does_not_fit_is_shortened_rather_than_dropped() -> None:
    plan = Plan((stop(1, "seaboard", 12),))
    found = measure(plan, {"seaboard": channel("seaboard", 10)}, {"seaboard": 4})
    cut = trim(plan, found)
    assert cut.stops[0].pages == 6
    assert any("shortened from 12 pages to 6" in line for line in cut.skipped)


def test_the_licences_the_planner_put_first_keep_their_pages() -> None:
    plan = Plan((stop(1, "seaboard", 6, 1), stop(2, "seaboard", 6, 2)))
    found = measure(plan, {"seaboard": channel("seaboard", 8)}, {})
    cut = trim(plan, found)
    assert [(item.licence_serial, item.pages) for item in cut.stops] == [(1, 6), (2, 2)]


def test_a_stop_with_no_room_left_at_all_is_dropped() -> None:
    plan = Plan((stop(1, "seaboard", 8), stop(2, "seaboard", 4)))
    found = measure(plan, {"seaboard": channel("seaboard", 8)}, {})
    cut = trim(plan, found)
    assert [item.licence_serial for item in cut.stops] == [1]
    assert any("requests are spent on this channel" in line for line in cut.skipped)


def test_a_stop_on_a_channel_with_no_allowance_is_left_where_it_is() -> None:
    plan = Plan((stop(1, "gone", 4),))
    assert trim(plan, Budget()).stops == plan.stops


def test_the_spend_reads_zero_for_a_channel_nobody_has_fetched_from_today() -> None:
    assert spend_by_channel(["seaboard", "quayside"], {"seaboard": 3}) == {
        "seaboard": 3,
        "quayside": 0,
    }


def test_a_budget_with_nothing_in_it_fits_and_says_nothing() -> None:
    assert Budget().fits
    assert Budget().lines() == ()
    assert Budget().wanted == 0
