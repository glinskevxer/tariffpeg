"""An error is not permission, and a five hundred read as a green light gets complained about."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.fetch.pacer import Pacer
from tariffpeg.fetch.replay import ReplayTransport
from tariffpeg.fetch.transport import Headers, Response
from tariffpeg.harvest.session import Outcome, Result, Session, capture_of
from tariffpeg.model.channel import Channel, CourtesyWindow, FetchPolicy, SyndicationClass
from tests.conftest import AGENT

AT = dt.datetime(2025, 7, 4, 12, 0, tzinfo=dt.UTC)
PAGE = "https://seaboard.example/p/1/reviews"
ROBOTS = "https://seaboard.example/robots.txt"


def channel(**over: object) -> Channel:
    base: dict[str, object] = {
        "slug": "seaboard",
        "name": "Seaboard Stays",
        "base_url": "https://seaboard.example",
        "syndication": SyndicationClass.PRIMARY,
        "policy": FetchPolicy(AGENT, 1500, 400),
    }
    base.update(over)
    return Channel(**base)  # type: ignore[arg-type]


@pytest.fixture
def transport() -> ReplayTransport:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\nDisallow: /admin\n")
    replay.add(PAGE, "<html>reviews</html>")
    return replay


def test_a_page_that_is_allowed_comes_back_with_a_capture(transport: ReplayTransport) -> None:
    found = Session(transport).fetch(channel(), PAGE, AT, "seaboard/v1", 4021)
    assert found.ok
    assert found.result is Result.FETCHED
    assert found.response is not None
    assert found.capture is not None
    assert found.capture.licence_serial == 4021
    assert found.capture.profile_key == "seaboard/v1"
    assert found.capture.fetched_at == AT


def test_the_robots_file_is_fetched_once_per_session(transport: ReplayTransport) -> None:
    session = Session(transport)
    session.fetch(channel(), PAGE, AT, "seaboard/v1")
    session.fetch(channel(), PAGE, AT + dt.timedelta(seconds=30), "seaboard/v1")
    assert transport.times_asked(ROBOTS) == 1


def test_forgetting_the_robots_file_makes_the_session_read_it_again(
    transport: ReplayTransport,
) -> None:
    session = Session(transport)
    session.fetch(channel(), PAGE, AT, "seaboard/v1")
    session.forget_robots("seaboard")
    session.fetch(channel(), PAGE, AT + dt.timedelta(seconds=30), "seaboard/v1")
    assert transport.times_asked(ROBOTS) == 2


def test_a_path_the_robots_file_disallows_is_refused(transport: ReplayTransport) -> None:
    blocked = "https://seaboard.example/admin/users"
    found = Session(transport).fetch(channel(), blocked, AT, "seaboard/v1")
    assert found.result is Result.REFUSED
    assert "disallows this path" in found.reason
    assert transport.times_asked(blocked) == 0


def test_a_url_that_is_not_on_the_channel_is_refused_before_anything_is_read() -> None:
    replay = ReplayTransport()
    found = Session(replay).fetch(channel(), "https://elsewhere.example/p/1", AT, "seaboard/v1")
    assert found.result is Result.REFUSED
    assert "not on this channel" in found.reason
    assert replay.calls == []


def test_a_missing_robots_file_forbids_nothing() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "", status=404)
    replay.add(PAGE, "<html>reviews</html>")
    assert Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1").ok


def test_a_robots_file_that_could_not_be_served_forbids_everything() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "", status=500)
    replay.add(PAGE, "<html>reviews</html>")
    assert Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1").result is Result.REFUSED


def test_a_robots_file_that_would_not_fetch_at_all_forbids_everything() -> None:
    replay = ReplayTransport()
    replay.add(PAGE, "<html>reviews</html>")
    assert Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1").result is Result.REFUSED


def test_a_published_crawl_delay_longer_than_the_agreement_is_the_one_kept() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\nCrawl-delay: 30\n")
    replay.add(PAGE, "<html>reviews</html>")
    assert Session(replay).delay_for(channel(), AT) == 30000


def test_a_published_delay_shorter_than_the_agreement_does_not_shorten_it(
    transport: ReplayTransport,
) -> None:
    assert Session(transport).delay_for(channel(), AT) == 1500


def test_the_crawl_delay_holds_the_second_request_back(transport: ReplayTransport) -> None:
    session = Session(transport)
    session.fetch(channel(), PAGE, AT, "seaboard/v1")
    found = session.fetch(channel(), PAGE, AT + dt.timedelta(milliseconds=100), "seaboard/v1")
    assert found.result is Result.HELD
    assert found.worth_retrying
    assert "crawl delay" in found.reason
    assert found.wait_ms == 1400


def test_a_shut_courtesy_window_holds_the_request_and_says_when_it_opens(
    transport: ReplayTransport,
) -> None:
    night = channel(policy=FetchPolicy(AGENT, 1500, 400, window=CourtesyWindow(22, 6)))
    found = Session(transport).fetch(night, PAGE, AT, "seaboard/v1")
    assert found.result is Result.HELD
    assert "courtesy window" in found.reason
    assert found.resume_at == AT.replace(hour=22)


def test_a_spent_daily_ceiling_holds_the_request(transport: ReplayTransport) -> None:
    small = channel(policy=FetchPolicy(AGENT, 1500, 2))
    session = Session(transport)
    assert session.fetch(small, PAGE, AT, "seaboard/v1").ok
    found = session.fetch(small, PAGE, AT + dt.timedelta(hours=1), "seaboard/v1")
    assert found.result is Result.HELD
    assert "daily ceiling" in found.reason


def test_the_robots_fetch_counts_against_the_daily_ceiling() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "<html>reviews</html>")
    pacer = Pacer()
    Session(replay, pacer).fetch(channel(), PAGE, AT, "seaboard/v1")
    assert pacer.spent_today("seaboard.example", AT) == 2


def test_a_conditional_request_that_comes_back_unchanged_is_reported_as_such() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "<html>reviews</html>", headers={"ETag": "abc"})
    found = Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1", etag="abc")
    assert found.result is Result.UNCHANGED
    assert found.capture is None


def test_a_page_that_answers_with_a_status_nobody_retries_is_a_failure() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "", status=451)
    found = Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1")
    assert found.result is Result.FAILED
    assert "status 451" in found.reason


def test_a_page_that_will_not_fetch_at_all_is_a_failure() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    found = Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1")
    assert found.result is Result.FAILED
    assert "nothing for this url" in found.reason


def test_a_failed_fetch_still_counts_against_the_ceiling() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    pacer = Pacer()
    Session(replay, pacer).fetch(channel(), PAGE, AT, "seaboard/v1")
    assert pacer.spent_today("seaboard.example", AT) == 2


def test_a_held_outcome_carries_no_page_and_did_not_succeed() -> None:
    held = Outcome(Result.HELD, PAGE, wait_ms=1400)
    assert not held.ok
    assert held.worth_retrying
    assert held.response is None


def test_a_recorded_robots_file_can_be_read_directly(transport: ReplayTransport) -> None:
    rules = Session(transport).robots_for(channel(), AT)
    assert rules.allows(AGENT, "/p/1/reviews")
    assert not rules.allows(AGENT, "/admin/users")


def test_a_session_can_be_handed_a_pacer_that_has_seen_traffic() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "page")
    pacer = Pacer()
    pacer.record("seaboard.example", AT)
    assert Session(replay, pacer).fetch(channel(), PAGE, AT, "seaboard/v1").result is Result.HELD


def test_a_response_is_recorded_as_a_capture() -> None:
    reply = Response(
        "https://seaboard.example/p/1/reviews?page=1",
        200,
        b"<html>page</html>",
        Headers({"ETag": "abc"}),
        elapsed_ms=142,
    )
    built = capture_of(reply, "seaboard", PAGE, AT, "seaboard/v1", 4021)
    assert built.digest == reply.digest
    assert built.redirected
    assert built.byte_count == len(b"<html>page</html>")
    assert built.etag == "abc"
    assert built.elapsed_ms == 142
    assert built.licence_serial == 4021
    assert built.fetched_at == AT


def test_a_channel_answering_with_a_server_error_is_worth_one_more_try() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "", status=503)
    found = Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1")
    assert found.result is Result.RETRY
    assert found.worth_retrying
    assert found.wait_ms > 0
    assert "worth one more try" in found.reason


def test_a_server_error_that_keeps_happening_stops_being_worth_a_try() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "", status=503)
    session = Session(replay)
    session.fetch(channel(), PAGE, AT, "seaboard/v1")
    found = session.fetch(channel(), PAGE, AT + dt.timedelta(seconds=30), "seaboard/v1")
    assert found.result is Result.FAILED
    assert session.attempts(PAGE) == 2


def test_a_channel_that_turns_us_away_is_left_alone_for_the_run() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "", status=429)
    session = Session(replay)
    first = session.fetch(channel(), PAGE, AT, "seaboard/v1")
    assert first.result is Result.REFUSED
    assert "turned us away with a 429" in first.reason
    assert session.turned_away("seaboard")
    later = session.fetch(channel(), PAGE, AT + dt.timedelta(hours=2), "seaboard/v1")
    assert later.result is Result.REFUSED
    assert replay.times_asked(PAGE) == 1


def test_a_forbidden_answer_turns_us_away_the_same_way() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "", status=403)
    found = Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1")
    assert found.result is Result.REFUSED
    assert "403" in found.reason


def test_the_wait_a_channel_asked_for_is_carried_through() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "", status=429, headers={"Retry-After": "600"})
    found = Session(replay).fetch(channel(), PAGE, AT, "seaboard/v1")
    assert found.wait_ms == 600_000
    assert found.resume_at == AT + dt.timedelta(minutes=10)


def test_a_channel_that_turns_us_away_does_not_stop_another_one() -> None:
    replay = ReplayTransport()
    replay.add(ROBOTS, "User-agent: *\n")
    replay.add(PAGE, "", status=429)
    replay.add("https://quayside.example/robots.txt", "User-agent: *\n")
    replay.add("https://quayside.example/p/1", "<html>reviews</html>")
    session = Session(replay)
    session.fetch(channel(), PAGE, AT, "seaboard/v1")
    other = channel(slug="quayside", base_url="https://quayside.example")
    assert session.fetch(other, "https://quayside.example/p/1", AT, "quayside/v1").ok


def test_a_url_nobody_has_asked_for_has_no_attempts_against_it() -> None:
    assert Session(ReplayTransport()).attempts(PAGE) == 0
    assert Session(ReplayTransport()).turned_away("seaboard") == ""
