"""What a fetch is, independent of what does the fetching.

The harvest never talks to the network directly. It talks to a transport, and
which transport it is holding decides whether a request goes out over the wire,
comes off a recorded fixture, or is refused. That is what lets the whole
pipeline be run against a bundle of captures years later and produce the same
answer it produced on the day.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from tariffpeg.errors import FetchFailed
from tariffpeg.ids import capture_digest

DEFAULT_ENCODING = "utf-8"
"""What a page is decoded as when it will not say."""

_CHARSET_IN_HEADER = re.compile(r"charset\s*=\s*['\"]?([A-Za-z0-9_.:-]+)")
_CHARSET_IN_META = re.compile(rb"<meta[^>]+charset\s*=\s*['\"]?([A-Za-z0-9_.:-]+)", re.I)


class Headers:
    """Response headers, looked up without caring about case."""

    def __init__(self, pairs: dict[str, str] | None = None) -> None:
        self._pairs = {key.lower(): value for key, value in (pairs or {}).items()}

    def get(self, name: str, default: str = "") -> str:
        """Return a header value, or the default if it is not there."""
        return self._pairs.get(name.lower(), default)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name.lower() in self._pairs

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Headers) and other.pairs() == self._pairs

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._pairs.items())))

    def __repr__(self) -> str:
        return f"Headers({self._pairs!r})"

    def pairs(self) -> dict[str, str]:
        """Return the underlying mapping, lowercased."""
        return dict(self._pairs)

    def items(self) -> tuple[tuple[str, str], ...]:
        """Return the headers in name order."""
        return tuple(sorted(self._pairs.items()))


@dataclass(frozen=True, slots=True)
class Request:
    """One page we intend to ask a channel for."""

    url: str
    user_agent: str
    etag: str | None = None
    modified_since: str | None = None

    def headers(self) -> dict[str, str]:
        """Return the headers this request goes out with."""
        sending = {"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"}
        if self.etag:
            sending["If-None-Match"] = self.etag
        if self.modified_since:
            sending["If-Modified-Since"] = self.modified_since
        return sending


@dataclass(frozen=True, slots=True)
class Response:
    """What came back, kept as bytes so the digest is over what was served."""

    url: str
    status: int
    body: bytes
    headers: Headers = field(default_factory=Headers)
    elapsed_ms: int = 0

    @property
    def digest(self) -> str:
        """Return the digest recorded against this response in the ledger."""
        return capture_digest(self.body)

    @property
    def ok(self) -> bool:
        """Return whether the response carries a page."""
        return 200 <= self.status < 300

    @property
    def unchanged(self) -> bool:
        """Return whether the channel said the page has not moved on."""
        return self.status == 304

    @property
    def missing(self) -> bool:
        """Return whether the channel says there is nothing at this url."""
        return self.status == 404

    @property
    def refused(self) -> bool:
        """Return whether the channel turned the request away.

        Four two nine and four oh three are the two that matter. Both mean stop
        rather than try again in a moment.
        """
        return self.status in (403, 429)

    def encoding(self) -> str:
        """Return the encoding this page should be decoded with.

        The header wins, then a meta tag in the first part of the body, then
        utf-8. Channels get this wrong often enough that guessing is part of the
        job, but guessing quietly is not.
        """
        declared = _CHARSET_IN_HEADER.search(self.headers.get("content-type"))
        if declared:
            return declared.group(1).lower()
        sniffed = _CHARSET_IN_META.search(self.body[:2048])
        if sniffed:
            return sniffed.group(1).decode("ascii", "replace").lower()
        return DEFAULT_ENCODING

    def text(self) -> str:
        """Return the body decoded, replacing anything that will not decode."""
        try:
            return self.body.decode(self.encoding(), "replace")
        except LookupError:
            return self.body.decode(DEFAULT_ENCODING, "replace")


class Transport(Protocol):
    """Something that can turn a request into a response."""

    def get(self, request: Request) -> Response:
        """Fetch one page, or raise :class:`FetchFailed`."""


class RefusingTransport:
    """A transport that will not fetch anything.

    This is the default everywhere. A caller that has not been handed a real
    transport gets a refusal rather than quietly reaching the network.
    """

    def get(self, request: Request) -> Response:
        """Refuse the request and say why."""
        raise FetchFailed(request.url, "no transport was supplied")
