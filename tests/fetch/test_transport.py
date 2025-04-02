"""Nothing reaches the network by accident, and a page that lies about its charset is handled."""

from __future__ import annotations

import pytest

from tariffpeg.errors import FetchFailed, TariffpegError
from tariffpeg.fetch.transport import (
    Headers,
    RefusingTransport,
    Request,
    Response,
)

AGENT = "tariffpeg-harvester (standards@example-authority.test)"


def test_headers_are_looked_up_without_caring_about_case() -> None:
    headers = Headers({"Content-Type": "text/html; charset=utf-8"})
    assert headers.get("content-type") == "text/html; charset=utf-8"
    assert headers.get("CONTENT-TYPE").startswith("text/html")
    assert "content-type" in headers
    assert "etag" not in headers
    assert headers.get("etag", "none") == "none"


def test_headers_compare_and_hash_on_their_contents() -> None:
    one = Headers({"ETag": "abc"})
    two = Headers({"etag": "abc"})
    assert one == two
    assert hash(one) == hash(two)
    assert one != Headers({"etag": "def"})
    assert one != "abc"
    assert "etag" in repr(one).lower()


def test_headers_list_in_name_order() -> None:
    headers = Headers({"Z": "1", "A": "2"})
    assert headers.items() == (("a", "2"), ("z", "1"))
    assert headers.pairs() == {"a": "2", "z": "1"}


def test_a_request_sends_the_agreed_agent_string() -> None:
    sending = Request("https://seaboard.example/p/1", AGENT).headers()
    assert sending["User-Agent"] == AGENT
    assert "Accept" in sending
    assert "If-None-Match" not in sending


def test_a_request_with_an_etag_asks_only_for_what_changed() -> None:
    sending = Request("https://x.example/p", AGENT, etag='W/"abc"').headers()
    assert sending["If-None-Match"] == 'W/"abc"'


def test_a_request_can_ask_by_date_instead() -> None:
    sending = Request("https://x.example/p", AGENT, modified_since="Wed, 21 Oct 2025 07:28:00 GMT")
    assert sending.headers()["If-Modified-Since"].startswith("Wed,")


def test_a_response_digests_the_bytes_that_were_served() -> None:
    one = Response("https://x.example", 200, b"<html>a</html>")
    two = Response("https://x.example", 200, b"<html>b</html>")
    assert one.digest.startswith("sha256:")
    assert one.digest != two.digest


def test_the_status_families_read_as_names() -> None:
    assert Response("u", 200, b"").ok
    assert Response("u", 204, b"").ok
    assert not Response("u", 304, b"").ok
    assert Response("u", 304, b"").unchanged
    assert Response("u", 404, b"").missing
    assert Response("u", 403, b"").refused
    assert Response("u", 429, b"").refused
    assert not Response("u", 500, b"").refused


def test_the_header_decides_the_encoding_when_it_says_so() -> None:
    headers = Headers({"Content-Type": "text/html; charset=latin-1"})
    response = Response("u", 200, "caf\u00e9".encode("latin-1"), headers)
    assert response.encoding() == "latin-1"
    assert response.text() == "caf\u00e9"


def test_a_meta_tag_is_used_when_the_header_is_silent() -> None:
    body = b"<html><head><meta charset='iso-8859-1'></head><body>caf\xe9</body></html>"
    response = Response("u", 200, body, Headers({"Content-Type": "text/html"}))
    assert response.encoding() == "iso-8859-1"
    assert "caf\u00e9" in response.text()


def test_a_meta_tag_past_the_first_part_of_the_page_is_not_looked_at() -> None:
    body = b"<html>" + b"x" * 4000 + b"<meta charset='iso-8859-1'>"
    assert Response("u", 200, body).encoding() == "utf-8"


def test_a_page_that_says_nothing_is_read_as_utf_eight() -> None:
    assert Response("u", 200, "caf\u00e9".encode()).text() == "caf\u00e9"


def test_a_page_that_names_an_encoding_python_has_never_heard_of_still_decodes() -> None:
    headers = Headers({"Content-Type": "text/html; charset=klingon-1"})
    response = Response("u", 200, b"hello", headers)
    assert response.encoding() == "klingon-1"
    assert response.text() == "hello"


def test_bytes_that_do_not_decode_are_replaced_rather_than_raising() -> None:
    headers = Headers({"Content-Type": "text/html; charset=utf-8"})
    assert "caf" in Response("u", 200, b"caf\xe9", headers).text()


def test_the_default_transport_refuses_rather_than_reaching_the_network() -> None:
    with pytest.raises(FetchFailed, match="no transport was supplied") as caught:
        RefusingTransport().get(Request("https://seaboard.example/p/1", AGENT))
    assert isinstance(caught.value, TariffpegError)
    assert caught.value.context() == {
        "url": "https://seaboard.example/p/1",
        "reason": "no transport was supplied",
    }
