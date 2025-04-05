"""A transport that answers out of a recording instead of off the wire.

Every test in this package holds one of these. That is not a convenience, it is
the rule: a suite that can reach the network is a suite whose results depend on
the uptime of somebody far away, and this one has to be runnable from an
evidence bundle on a machine with no network at all.

The strict setting is on by default. A url the recording does not know about is
a failure rather than an empty page, because a profile that has drifted onto the
wrong url would otherwise look exactly like a property with no reviews.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from tariffpeg.errors import FetchFailed
from tariffpeg.fetch.transport import Headers, Request, Response


class ReplayTransport:
    """Answers requests from a recording, and remembers what was asked."""

    def __init__(self, pages: Mapping[str, Response] | None = None, strict: bool = True) -> None:
        self._pages: dict[str, list[Response]] = {}
        self._served: dict[str, int] = {}
        self.calls: list[Request] = []
        self.strict = strict
        for url, response in (pages or {}).items():
            self._pages[url] = [response]

    def add(
        self,
        url: str,
        body: bytes | str = b"",
        status: int = 200,
        headers: Mapping[str, str] | None = None,
        elapsed_ms: int = 0,
    ) -> None:
        """Record what this url answers with."""
        payload = body.encode() if isinstance(body, str) else body
        response = Response(url, status, payload, Headers(dict(headers or {})), elapsed_ms)
        self._pages[url] = [response]

    def add_sequence(self, url: str, responses: Iterable[Response]) -> None:
        """Record a run of answers for a url, served one per request.

        The last one repeats once the run is used up, so a test for a retry can
        record a failure and a success without saying what happens on the third
        try, which nothing asks for.
        """
        run = list(responses)
        if not run:
            raise ValueError("a recorded sequence needs at least one response in it")
        self._pages[url] = run

    def known(self) -> tuple[str, ...]:
        """Return the urls this recording can answer, in order."""
        return tuple(sorted(self._pages))

    def times_asked(self, url: str) -> int:
        """Return how many times this url has been requested."""
        return sum(1 for call in self.calls if call.url == url)

    def urls_asked(self) -> tuple[str, ...]:
        """Return the urls that were requested, in the order they were asked for."""
        return tuple(call.url for call in self.calls)

    def get(self, request: Request) -> Response:
        """Answer a request out of the recording."""
        self.calls.append(request)
        run = self._pages.get(request.url)
        if run is None:
            if self.strict:
                raise FetchFailed(request.url, "the recording has nothing for this url")
            return Response(request.url, 404, b"")
        index = min(self._served.get(request.url, 0), len(run) - 1)
        self._served[request.url] = index + 1
        response = run[index]
        if request.etag and response.headers.get("etag") == request.etag:
            return Response(request.url, 304, b"", response.headers, response.elapsed_ms)
        return response

    def reset(self) -> None:
        """Forget what has been asked, keeping the recording itself."""
        self.calls.clear()
        self._served.clear()
