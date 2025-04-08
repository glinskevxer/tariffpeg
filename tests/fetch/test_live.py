"""A redirect that leaves the host walks out from under the robots file we read."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from tariffpeg.errors import FetchFailed, Refused
from tariffpeg.fetch.live import (
    MAX_BODY_BYTES,
    LiveTransport,
    Timeouts,
    build_client,
    host_of,
    resolve,
)
from tariffpeg.fetch.transport import Request

AGENT = "tariffpeg-harvester (standards@example-authority.test)"
URL = "https://seaboard.example/p/1"


Handler = Callable[[httpx.Request], httpx.Response]


def live_for(handler: Handler, max_redirects: int = 4) -> LiveTransport:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    return LiveTransport(client, max_redirects=max_redirects)


def serving(body: bytes = b"page", status: int = 200, **headers: str) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body, headers=headers)

    return handler


def test_timeouts_convert_to_the_seconds_the_client_wants() -> None:
    timeout = Timeouts(connect_ms=1500, read_ms=9000).as_httpx()
    assert timeout.connect == 1.5
    assert timeout.read == 9.0


def test_the_client_is_built_with_redirects_off_because_we_follow_them() -> None:
    client = build_client(Timeouts())
    try:
        assert client.follow_redirects is False
    finally:
        client.close()


def test_the_host_is_read_off_a_url_without_its_port() -> None:
    assert host_of("https://seaboard.example:8443/p/1") == "seaboard.example"
    assert host_of("https://SEABOARD.example/p") == "seaboard.example"
    assert host_of("not a url") == ""


def test_an_absolute_location_is_used_as_it_stands() -> None:
    assert resolve(URL, "https://other.example/x") == "https://other.example/x"


def test_a_rooted_location_keeps_the_scheme_and_the_host() -> None:
    assert resolve(URL, "/p/2") == "https://seaboard.example/p/2"


def test_a_scheme_relative_location_keeps_the_scheme() -> None:
    assert resolve(URL, "//other.example/x") == "https://other.example"


def test_a_relative_location_hangs_off_the_directory_it_came_from() -> None:
    assert resolve("https://seaboard.example/p/1/reviews", "page2") == (
        "https://seaboard.example/p/1/page2"
    )


def test_a_page_comes_back_with_its_status_body_and_headers() -> None:
    with live_for(serving(b"<html>hi</html>", 200, **{"content-type": "text/html"})) as live:
        response = live.get(Request(URL, AGENT))
        assert response.status == 200
        assert response.body == b"<html>hi</html>"
        assert response.headers.get("content-type") == "text/html"
        assert response.url == URL


def test_the_agreed_agent_string_goes_out_on_the_request() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, content=b"page")

    with live_for(handler) as live:
        live.get(Request(URL, AGENT))
    assert seen == [AGENT]


def test_a_same_host_redirect_is_followed_and_the_final_url_is_recorded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/p/1":
            return httpx.Response(301, headers={"location": "/p/1/reviews"})
        return httpx.Response(200, content=b"reviews")

    with live_for(handler) as live:
        response = live.get(Request(URL, AGENT))
        assert response.status == 200
        assert response.url == "https://seaboard.example/p/1/reviews"


def test_a_redirect_off_the_host_is_refused_and_says_which_host_we_checked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://mirror.example/p/1"})

    with live_for(handler) as live, pytest.raises(Refused, match="leaves seaboard.example"):
        live.get(Request(URL, AGENT))


def test_a_redirect_with_no_location_header_is_a_failure() -> None:
    with (
        live_for(serving(b"", 302)) as live,
        pytest.raises(FetchFailed, match="no location header"),
    ):
        live.get(Request(URL, AGENT))


def test_a_redirect_loop_stops_at_the_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/p/1"})

    with (
        live_for(handler, max_redirects=2) as live,
        pytest.raises(FetchFailed, match="than 2"),
    ):
        live.get(Request(URL, AGENT))


def test_a_url_that_is_not_https_is_refused_before_anything_is_sent() -> None:
    with live_for(serving()) as live, pytest.raises(Refused, match="https only"):
        live.get(Request("http://seaboard.example/p/1", AGENT))


def test_a_timeout_is_reported_as_a_fetch_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with live_for(handler) as live, pytest.raises(FetchFailed, match="did not answer in time"):
        live.get(Request(URL, AGENT))


def test_any_other_transport_error_is_reported_with_what_it_said() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name or service not known", request=request)

    with live_for(handler) as live, pytest.raises(FetchFailed, match="did not complete"):
        live.get(Request(URL, AGENT))


def test_a_page_bigger_than_the_limit_is_refused_rather_than_parsed() -> None:
    with (
        live_for(serving(b"x" * (MAX_BODY_BYTES + 1))) as live,
        pytest.raises(FetchFailed, match="larger than"),
    ):
        live.get(Request(URL, AGENT))


def test_a_transport_with_no_client_builds_one_and_closes_it() -> None:
    live = LiveTransport()
    assert live.client is not None
    live.close()
    assert live.client.is_closed
