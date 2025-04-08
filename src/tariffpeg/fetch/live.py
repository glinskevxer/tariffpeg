"""The transport that actually talks to a channel.

Redirects are followed here rather than by the client, for one reason: the
robots file we read belongs to a host, and a redirect that lands on a different
host has walked out from under the permission we checked. That hop is refused
and recorded, not followed and hoped about.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from types import TracebackType
from urllib.parse import urlsplit, urlunsplit

import httpx

from tariffpeg.errors import FetchFailed, Refused
from tariffpeg.fetch.transport import Headers, Request, Response

MAX_BODY_BYTES = 4 * 1024 * 1024
"""A review page past four megabytes is a page we have misidentified."""


@dataclass(frozen=True, slots=True)
class Timeouts:
    """How long the reader is willing to wait, in milliseconds."""

    connect_ms: int = 5_000
    read_ms: int = 15_000
    write_ms: int = 5_000
    pool_ms: int = 5_000

    def as_httpx(self) -> httpx.Timeout:
        """Return these as the client wants them."""
        return httpx.Timeout(
            connect=self.connect_ms / 1000,
            read=self.read_ms / 1000,
            write=self.write_ms / 1000,
            pool=self.pool_ms / 1000,
        )


def host_of(url: str) -> str:
    """Return the host part of a url, lowercased and without the port."""
    return urlsplit(url).hostname or ""


def resolve(base: str, location: str) -> str:
    """Return the absolute url a Location header points at."""
    parts = urlsplit(location)
    if parts.scheme and parts.netloc:
        return location
    origin = urlsplit(base)
    if location.startswith("//"):
        return urlunsplit((origin.scheme, location[2:].split("/", 1)[0], "", "", ""))
    if location.startswith("/"):
        return urlunsplit((origin.scheme, origin.netloc, location, "", ""))
    trimmed = origin.path.rsplit("/", 1)[0]
    return urlunsplit((origin.scheme, origin.netloc, f"{trimmed}/{location}", "", ""))


def build_client(timeouts: Timeouts | None = None) -> httpx.Client:
    """Return a client with redirects off, because this module follows them."""
    return httpx.Client(
        timeout=(timeouts or Timeouts()).as_httpx(),
        follow_redirects=False,
        http2=False,
    )


class LiveTransport:
    """Fetches over the wire, following redirects only within one host."""

    def __init__(self, client: httpx.Client | None = None, max_redirects: int = 4) -> None:
        self.client = client if client is not None else build_client()
        self.max_redirects = max_redirects

    def __enter__(self) -> LiveTransport:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying client."""
        self.client.close()

    def get(self, request: Request) -> Response:
        """Fetch a page, following same host redirects and refusing the rest."""
        if not request.url.startswith("https://"):
            raise Refused(request.url, "channels are read over https only")
        origin = host_of(request.url)
        url = request.url
        for _ in range(self.max_redirects + 1):
            reply = self._one(url, request)
            if reply.status not in (301, 302, 303, 307, 308):
                return reply
            location = reply.headers.get("location")
            if not location:
                raise FetchFailed(url, f"status {reply.status} with no location header")
            url = resolve(url, location)
            if host_of(url) != origin:
                raise Refused(url, f"the redirect leaves {origin}, which is the host we checked")
        raise FetchFailed(request.url, f"more than {self.max_redirects} redirects")

    def _one(self, url: str, request: Request) -> Response:
        started = time.monotonic()
        try:
            reply = self.client.get(url, headers=request.headers())
        except httpx.TimeoutException as err:
            raise FetchFailed(url, "the channel did not answer in time") from err
        except httpx.HTTPError as err:
            raise FetchFailed(url, f"the request did not complete: {err}") from err
        elapsed_ms = int((time.monotonic() - started) * 1000)
        body = reply.content
        if len(body) > MAX_BODY_BYTES:
            raise FetchFailed(url, f"the page is larger than {MAX_BODY_BYTES} bytes")
        return Response(
            url=url,
            status=reply.status_code,
            body=body,
            headers=Headers(dict(reply.headers)),
            elapsed_ms=elapsed_ms,
        )
