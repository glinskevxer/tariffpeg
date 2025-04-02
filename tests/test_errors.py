"""The error hierarchy has to survive being caught by the base class."""

from __future__ import annotations

import pytest

from tariffpeg.errors import (
    AlreadyExists,
    Conflict,
    FetchFailed,
    Invalid,
    NotFound,
    Refused,
    TariffpegError,
)


def test_every_error_is_catchable_as_the_base() -> None:
    raised = [
        NotFound("licence", "L-0001"),
        AlreadyExists("channel", "seaboard"),
        Invalid("bed_count", -3, "a bed count cannot be negative"),
        Conflict("remediation notice", "it predates the contradiction it clears"),
    ]
    for err in raised:
        assert isinstance(err, TariffpegError)


def test_the_codes_are_distinct_so_the_cli_can_map_them_to_exit_codes() -> None:
    codes = {
        NotFound.code,
        AlreadyExists.code,
        Invalid.code,
        Conflict.code,
        TariffpegError.code,
        FetchFailed.code,
        Refused.code,
    }
    assert len(codes) == 7


def test_not_found_names_the_kind_and_the_reference_in_the_message() -> None:
    err = NotFound("licence", "L-0042")
    assert "licence" in str(err)
    assert "L-0042" in str(err)
    assert err.context() == {"kind": "licence", "ref": "L-0042"}


def test_already_exists_reads_as_a_registration_refusal() -> None:
    err = AlreadyExists("channel", "seaboard")
    assert str(err) == "channel 'seaboard' is already registered"
    assert err.context()["kind"] == "channel"


def test_invalid_carries_the_field_the_value_and_the_reason() -> None:
    err = Invalid("crawl_delay_ms", 0, "the channel published a delay of 2000")
    assert err.field == "crawl_delay_ms"
    assert err.value == 0
    assert "published a delay" in err.reason
    assert err.context() == {
        "field": "crawl_delay_ms",
        "value": "0",
        "reason": "the channel published a delay of 2000",
    }


def test_conflict_says_what_cannot_be_applied() -> None:
    err = Conflict("remediation notice", "it predates the contradiction it clears")
    assert str(err).startswith("remediation notice cannot be applied")
    assert err.context()["subject"] == "remediation notice"


def test_the_base_error_carries_no_context_of_its_own() -> None:
    assert TariffpegError("something went wrong").context() == {}


def test_the_errors_can_be_raised_and_caught_by_their_own_type() -> None:
    with pytest.raises(NotFound) as caught:
        raise NotFound("capture", "sha256:deadbeef")
    assert caught.value.ref == "sha256:deadbeef"

    with pytest.raises(Invalid):
        raise Invalid("season", "monsoon", "the calendar has three seasons")


def test_a_fetch_failure_names_the_url_and_the_reason() -> None:
    err = FetchFailed("https://seaboard.example/p/1", "the connection timed out")
    assert "seaboard.example" in str(err)
    assert err.context() == {
        "url": "https://seaboard.example/p/1",
        "reason": "the connection timed out",
    }


def test_a_refusal_names_the_term_that_held_the_request_back() -> None:
    err = Refused("https://seaboard.example/p/1", "the robots file disallows this path")
    assert err.term.startswith("the robots file")
    assert err.context()["url"].endswith("/p/1")
    assert isinstance(err, TariffpegError)


def test_the_fetch_codes_are_distinct_from_the_store_ones() -> None:
    assert len({FetchFailed.code, Refused.code, NotFound.code, Invalid.code}) == 4
