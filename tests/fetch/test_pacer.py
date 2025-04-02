"""A caller that is held back is told which of the three terms is holding it."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.fetch.pacer import Grant, Hold, Pacer
from tariffpeg.model.channel import ALWAYS, CourtesyWindow, FetchPolicy

AGENT = "tariffpeg-harvester (standards@example-authority.test)"
HOST = "seaboard.example"


def policy(**over: object) -> FetchPolicy:
    base: dict[str, object] = {
        "user_agent": AGENT,
        "crawl_delay_ms": 2000,
        "daily_request_ceiling": 3,
        "window": ALWAYS,
    }
    base.update(over)
    return FetchPolicy(**base)  # type: ignore[arg-type]


def at(hour: int = 10, minute: int = 0, second: int = 0, day: int = 12) -> dt.datetime:
    return dt.datetime(2025, 6, day, hour, minute, second, tzinfo=dt.UTC)


def test_the_first_request_to_a_host_goes_straight_out() -> None:
    grant = Pacer().ask(HOST, policy(), at())
    assert grant.allowed
    assert grant.hold is Hold.READY
    assert grant.wait_ms == 0


def test_the_second_request_waits_out_the_crawl_delay() -> None:
    pacer = Pacer()
    pacer.record(HOST, at())
    grant = pacer.ask(HOST, policy(), at(second=1))
    assert not grant.allowed
    assert grant.hold is Hold.CRAWL_DELAY
    assert grant.wait_ms == 1000
    assert grant.resume_at == at(second=2)


def test_once_the_delay_has_passed_the_request_goes_out() -> None:
    pacer = Pacer()
    pacer.record(HOST, at())
    assert pacer.ask(HOST, policy(), at(second=2)).allowed


def test_the_longer_of_the_two_delays_is_the_one_that_is_waited_out() -> None:
    pacer = Pacer()
    pacer.record(HOST, at())
    grant = pacer.ask(HOST, policy(), at(second=2), delay_ms=5000)
    assert grant.hold is Hold.CRAWL_DELAY
    assert grant.wait_ms == 3000


def test_a_published_delay_shorter_than_the_agreement_does_not_shorten_it() -> None:
    pacer = Pacer()
    pacer.record(HOST, at())
    grant = pacer.ask(HOST, policy(), at(second=1), delay_ms=100)
    assert grant.wait_ms == 1000


def test_each_host_is_paced_on_its_own() -> None:
    pacer = Pacer()
    pacer.record(HOST, at())
    assert pacer.ask("other.example", policy(), at()).allowed
    assert not pacer.ask(HOST, policy(), at()).allowed


def test_a_closed_courtesy_window_holds_the_request_until_it_opens() -> None:
    night = policy(window=CourtesyWindow(22, 6))
    grant = Pacer().ask(HOST, night, at(hour=12))
    assert grant.hold is Hold.COURTESY_WINDOW
    assert grant.resume_at == at(hour=22)
    assert grant.wait_ms == 10 * 3600 * 1000


def test_the_window_is_checked_before_the_crawl_delay() -> None:
    night = policy(window=CourtesyWindow(22, 6))
    pacer = Pacer()
    pacer.record(HOST, at(hour=5, minute=59, second=59))
    grant = pacer.ask(HOST, night, at(hour=6, minute=0, second=0))
    assert grant.hold is Hold.COURTESY_WINDOW


def test_the_daily_ceiling_stops_the_host_for_the_rest_of_the_day() -> None:
    pacer = Pacer()
    for second in (0, 2, 4):
        assert pacer.ask(HOST, policy(), at(second=second)).allowed
        pacer.record(HOST, at(second=second))
    grant = pacer.ask(HOST, policy(), at(second=10))
    assert grant.hold is Hold.DAILY_CEILING
    assert grant.exhausted
    assert grant.resume_at == dt.datetime(2025, 6, 13, tzinfo=dt.UTC)


def test_the_ceiling_is_checked_before_anything_else() -> None:
    night = policy(window=CourtesyWindow(22, 6), daily_request_ceiling=1)
    pacer = Pacer()
    pacer.record(HOST, at(hour=23))
    grant = pacer.ask(HOST, night, at(hour=23, minute=30))
    assert grant.hold is Hold.DAILY_CEILING


def test_the_ceiling_resets_when_the_utc_day_rolls_over() -> None:
    pacer = Pacer()
    for second in (0, 2, 4):
        pacer.record(HOST, at(second=second))
    assert pacer.spent_today(HOST, at()) == 3
    assert pacer.spent_today(HOST, at(day=13)) == 0
    assert pacer.ask(HOST, policy(), at(day=13)).allowed


def test_recording_on_a_new_day_starts_the_count_again() -> None:
    pacer = Pacer()
    pacer.record(HOST, at())
    pacer.record(HOST, at(day=13))
    assert pacer.spent_today(HOST, at(day=13)) == 1


def test_the_spend_is_zero_for_a_host_nothing_has_gone_to() -> None:
    assert Pacer().spent_today("nowhere.example", at()) == 0


def test_the_pacer_insists_on_an_aware_instant() -> None:
    with pytest.raises(Invalid, match="asked in UTC"):
        Pacer().ask(HOST, policy(), dt.datetime(2025, 6, 12, 10, 0))


def test_a_host_can_be_forgotten_and_starts_clean() -> None:
    pacer = Pacer()
    pacer.record(HOST, at())
    assert pacer.hosts() == (HOST,)
    pacer.forget(HOST)
    assert pacer.hosts() == ()
    assert pacer.ask(HOST, policy(), at()).allowed


def test_forgetting_a_host_nothing_is_known_about_is_harmless() -> None:
    Pacer().forget("nowhere.example")


def test_the_hosts_come_back_in_order() -> None:
    pacer = Pacer()
    for host in ("quayside.example", "atlas.example", HOST):
        pacer.record(host, at())
    assert pacer.hosts() == ("atlas.example", "quayside.example", "seaboard.example")


def test_a_ready_grant_reports_no_wait_and_is_not_exhausted() -> None:
    grant = Grant(Hold.READY, 0)
    assert grant.allowed
    assert not grant.exhausted
