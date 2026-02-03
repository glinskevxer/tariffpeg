"""Trying again after a channel says stop is not a retry, it is ignoring them."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.fetch.backoff import (
    DEFAULT,
    TURNED_AWAY,
    WORTH_ANOTHER_TRY,
    Backoff,
    retry_after_ms,
)

NOW = dt.datetime(2026, 6, 1, 12, 0, tzinfo=dt.UTC)


def test_the_two_kinds_of_answer_do_not_overlap() -> None:
    assert not TURNED_AWAY & WORTH_ANOTHER_TRY
    assert 429 in TURNED_AWAY
    assert 503 in WORTH_ANOTHER_TRY


def test_the_wait_grows_with_every_attempt() -> None:
    backoff = Backoff(tries=4, first_wait_ms=1000, multiplier=3)
    assert backoff.wait_after(1) == 1000
    assert backoff.wait_after(2) == 3000
    assert backoff.wait_after(3) == 9000


def test_the_wait_stops_growing_at_the_longest_one() -> None:
    backoff = Backoff(tries=9, first_wait_ms=1000, multiplier=10, longest_wait_ms=5000)
    assert backoff.wait_after(4) == 5000


def test_an_attempt_before_the_first_one_is_refused() -> None:
    with pytest.raises(Invalid, match="counted from one"):
        DEFAULT.wait_after(0)


def test_a_request_is_worth_another_try_until_the_tries_run_out() -> None:
    backoff = Backoff(tries=2)
    assert backoff.worth_another(1)
    assert not backoff.worth_another(2)
    assert not backoff.worth_another(9)


def test_a_backoff_that_gets_shorter_is_refused() -> None:
    with pytest.raises(Invalid, match="does not get shorter"):
        Backoff(multiplier=0)


def test_a_backoff_that_never_tries_is_refused() -> None:
    with pytest.raises(Invalid, match="at least once"):
        Backoff(tries=0)


def test_a_wait_of_nothing_is_refused() -> None:
    with pytest.raises(Invalid, match="a millisecond or more"):
        Backoff(first_wait_ms=0)


def test_a_longest_wait_under_the_first_one_is_refused() -> None:
    with pytest.raises(Invalid, match="at least the first one"):
        Backoff(first_wait_ms=5000, longest_wait_ms=1000)


def test_a_retry_after_in_seconds_is_read() -> None:
    assert retry_after_ms("30", NOW) == 30_000
    assert retry_after_ms("2.5", NOW) == 2_500


def test_a_retry_after_as_a_date_is_read_against_the_clock() -> None:
    later = "Mon, 01 Jun 2026 12:01:00 GMT"
    assert retry_after_ms(later, NOW) == 60_000


def test_a_retry_after_in_the_past_reads_as_no_wait() -> None:
    earlier = "Mon, 01 Jun 2026 11:00:00 GMT"
    assert retry_after_ms(earlier, NOW) == 0
    assert retry_after_ms("-30", NOW) == 0


def test_a_retry_after_that_is_neither_reads_as_nothing() -> None:
    assert retry_after_ms("soon", NOW) is None
    assert retry_after_ms("", NOW) is None
    assert retry_after_ms("   ", NOW) is None


def test_the_default_backoff_tries_twice() -> None:
    assert DEFAULT.tries == 2
    assert DEFAULT.worth_another(1)
