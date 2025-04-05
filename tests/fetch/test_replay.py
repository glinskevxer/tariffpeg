"""The suite cannot reach the network, and a url nobody recorded is a failure."""

from __future__ import annotations

import pytest

from tariffpeg.errors import FetchFailed
from tariffpeg.fetch.replay import ReplayTransport
from tariffpeg.fetch.transport import Headers, Request, Response

AGENT = "tariffpeg-harvester (standards@example-authority.test)"
URL = "https://seaboard.example/p/1"
TAG_ONE = 'W/"v1"'
TAG_TWO = 'W/"v2"'


def ask(transport: ReplayTransport, url: str = URL, etag: str | None = None) -> Response:
    return transport.get(Request(url, AGENT, etag=etag))


def test_a_recorded_page_comes_back_as_it_was_recorded() -> None:
    transport = ReplayTransport()
    transport.add(URL, "<html>hello</html>", headers={"Content-Type": "text/html"})
    response = ask(transport)
    assert response.status == 200
    assert response.text() == "<html>hello</html>"
    assert response.headers.get("content-type") == "text/html"


def test_a_body_given_as_bytes_is_kept_as_bytes() -> None:
    transport = ReplayTransport()
    transport.add(URL, b"\xff\xfe binary")
    assert ask(transport).body == b"\xff\xfe binary"


def test_a_url_the_recording_does_not_know_is_a_failure() -> None:
    with pytest.raises(FetchFailed, match="nothing for this url"):
        ask(ReplayTransport())


def test_a_loose_recording_answers_a_missing_url_with_four_oh_four() -> None:
    assert ask(ReplayTransport(strict=False)).missing


def test_the_transport_can_be_built_from_a_mapping_of_responses() -> None:
    transport = ReplayTransport({URL: Response(URL, 200, b"page")})
    assert ask(transport).body == b"page"
    assert transport.known() == (URL,)


def test_every_request_is_remembered_in_order() -> None:
    transport = ReplayTransport(strict=False)
    for path in ("/p/1", "/p/2", "/p/1"):
        ask(transport, f"https://seaboard.example{path}")
    assert transport.urls_asked() == (
        "https://seaboard.example/p/1",
        "https://seaboard.example/p/2",
        "https://seaboard.example/p/1",
    )
    assert transport.times_asked("https://seaboard.example/p/1") == 2
    assert transport.times_asked("https://seaboard.example/p/9") == 0


def test_a_recorded_sequence_is_served_one_answer_per_request() -> None:
    transport = ReplayTransport()
    transport.add_sequence(
        URL,
        [Response(URL, 429, b""), Response(URL, 500, b""), Response(URL, 200, b"page")],
    )
    assert ask(transport).status == 429
    assert ask(transport).status == 500
    assert ask(transport).status == 200


def test_the_last_answer_in_a_sequence_repeats_once_the_run_is_used_up() -> None:
    transport = ReplayTransport()
    transport.add_sequence(URL, [Response(URL, 500, b""), Response(URL, 200, b"page")])
    ask(transport)
    assert ask(transport).status == 200
    assert ask(transport).status == 200


def test_an_empty_sequence_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one response"):
        ReplayTransport().add_sequence(URL, [])


def test_a_conditional_request_that_matches_comes_back_unchanged() -> None:
    transport = ReplayTransport()
    transport.add(URL, "page", headers={"ETag": TAG_ONE})
    assert ask(transport).status == 200
    unchanged = ask(transport, etag=TAG_ONE)
    assert unchanged.unchanged
    assert unchanged.body == b""


def test_a_conditional_request_with_a_stale_tag_gets_the_page() -> None:
    transport = ReplayTransport()
    transport.add(URL, "page", headers={"ETag": TAG_TWO})
    assert ask(transport, etag=TAG_ONE).status == 200


def test_recording_over_a_url_replaces_what_was_there() -> None:
    transport = ReplayTransport()
    transport.add(URL, "old")
    transport.add(URL, "new")
    assert ask(transport).text() == "new"


def test_resetting_forgets_the_calls_but_keeps_the_recording() -> None:
    transport = ReplayTransport()
    transport.add(URL, "page")
    ask(transport)
    transport.reset()
    assert transport.urls_asked() == ()
    assert ask(transport).text() == "page"


def test_resetting_puts_a_sequence_back_to_its_first_answer() -> None:
    transport = ReplayTransport()
    transport.add_sequence(URL, [Response(URL, 500, b""), Response(URL, 200, b"page")])
    ask(transport)
    ask(transport)
    transport.reset()
    assert ask(transport).status == 500


def test_the_headers_recorded_are_the_headers_served() -> None:
    transport = ReplayTransport()
    transport.add(URL, "page", headers={"ETag": "abc", "Content-Type": "text/html"})
    assert ask(transport).headers == Headers({"etag": "abc", "content-type": "text/html"})
