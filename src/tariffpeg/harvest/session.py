"""The polite reader: robots, the pacer and the transport, in that order.

The order is the point. The robots file is read first because there is no sense
pacing a request that is not allowed to go out at all. The pacer is asked
second. Only then does anything reach the transport.

A session does not sleep. It says how long the caller would have to wait and
leaves the waiting to whoever owns the clock, which is what lets a whole harvest
be replayed against a recording in a few milliseconds.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from tariffpeg.errors import FetchFailed, Refused
from tariffpeg.fetch import robots as robots_reader
from tariffpeg.fetch.backoff import DEFAULT as DEFAULT_BACKOFF
from tariffpeg.fetch.backoff import TURNED_AWAY, WORTH_ANOTHER_TRY, Backoff, retry_after_ms
from tariffpeg.fetch.live import host_of
from tariffpeg.fetch.pacer import Grant, Hold, Pacer
from tariffpeg.fetch.transport import Request, Response, Transport
from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel


def capture_of(
    response: Response,
    channel: str,
    requested_url: str,
    fetched_at: dt.datetime,
    profile_key: str,
    licence_serial: int | None = None,
) -> Capture:
    """Record a response as a capture.

    This lives here rather than on the capture itself. A capture is a record in
    the book, and the book has no business knowing what an http response looks
    like.
    """
    return Capture(
        digest=response.digest,
        channel=channel,
        url=requested_url,
        final_url=response.url,
        status=response.status,
        fetched_at=fetched_at,
        byte_count=len(response.body),
        profile_key=profile_key,
        elapsed_ms=response.elapsed_ms,
        licence_serial=licence_serial,
        etag=response.headers.get("etag"),
    )


class Result(StrEnum):
    """What came of asking for one page."""

    FETCHED = "fetched"
    UNCHANGED = "unchanged"
    HELD = "held"
    RETRY = "retry"
    REFUSED = "refused"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one attempt at one page produced."""

    result: Result
    url: str
    response: Response | None = None
    capture: Capture | None = None
    wait_ms: int = 0
    resume_at: dt.datetime | None = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        """Return whether a page came back."""
        return self.result is Result.FETCHED

    @property
    def worth_retrying(self) -> bool:
        """Return whether waiting would help."""
        return self.result in (Result.HELD, Result.RETRY)


class Session:
    """One harvest run against one set of channels."""

    def __init__(
        self,
        transport: Transport,
        pacer: Pacer | None = None,
        backoff: Backoff = DEFAULT_BACKOFF,
    ) -> None:
        self.transport = transport
        self.pacer = pacer if pacer is not None else Pacer()
        self.backoff = backoff
        self._robots: dict[str, robots_reader.Robots] = {}
        self._turned_away: dict[str, str] = {}
        self._attempts: dict[str, int] = {}

    def turned_away(self, slug: str) -> str:
        """Return why a channel is being left alone, or an empty string."""
        return self._turned_away.get(slug, "")

    def attempts(self, url: str) -> int:
        """Return how many times this run has asked for a url."""
        return self._attempts.get(url, 0)

    def robots_for(self, channel: Channel, at: dt.datetime) -> robots_reader.Robots:
        """Return the robots file for a channel, fetching it once per session.

        A channel that cannot serve its robots file is read as forbidding
        everything. An error is not permission, and a harvest that treats a five
        hundred as a green light is a harvest that will be complained about.
        """
        if channel.slug in self._robots:
            return self._robots[channel.slug]
        request = Request(channel.robots_url(), channel.policy.user_agent)
        try:
            reply = self.transport.get(request)
        except FetchFailed:
            found = robots_reader.ALLOW_NOTHING
        else:
            if reply.missing:
                found = robots_reader.ALLOW_EVERYTHING
            elif not reply.ok:
                found = robots_reader.ALLOW_NOTHING
            else:
                found = robots_reader.parse(reply.text())
        self.pacer.record(host_of(channel.robots_url()), at, paced=False)
        self._robots[channel.slug] = found
        return found

    def forget_robots(self, slug: str) -> None:
        """Drop the cached robots file for a channel."""
        self._robots.pop(slug, None)

    def delay_for(self, channel: Channel, at: dt.datetime) -> int:
        """Return the delay in force for a channel once its robots file is read."""
        published = self.robots_for(channel, at).crawl_delay_ms(channel.policy.user_agent)
        return channel.policy.delay_with(published)

    def fetch(
        self,
        channel: Channel,
        url: str,
        at: dt.datetime,
        profile_key: str,
        licence_serial: int | None = None,
        etag: str | None = None,
    ) -> Outcome:
        """Ask for one page, obeying the robots file and the agreed terms."""
        if not url.startswith(channel.base_url):
            return Outcome(Result.REFUSED, url, reason="that url is not on this channel")
        already = self.turned_away(channel.slug)
        if already:
            return Outcome(Result.REFUSED, url, reason=already)
        path = url[len(channel.base_url) :] or "/"
        rules = self.robots_for(channel, at)
        if not rules.allows(channel.policy.user_agent, path):
            return Outcome(Result.REFUSED, url, reason="the robots file disallows this path")
        published = rules.crawl_delay_ms(channel.policy.user_agent)
        grant = self.pacer.ask(channel.host(), channel.policy, at, published)
        if not grant.allowed:
            return self._held(url, grant)
        request = Request(url, channel.policy.user_agent, etag=etag)
        try:
            reply = self.transport.get(request)
        except (FetchFailed, Refused) as err:
            self.pacer.record(channel.host(), at)
            return Outcome(Result.FAILED, url, reason=str(err))
        self.pacer.record(channel.host(), at)
        self._attempts[url] = self.attempts(url) + 1
        if reply.status in TURNED_AWAY:
            return self._turn_away(channel.slug, url, reply, at)
        if reply.status in WORTH_ANOTHER_TRY and self.backoff.worth_another(self.attempts(url)):
            return Outcome(
                Result.RETRY,
                url,
                response=reply,
                wait_ms=self.backoff.wait_after(self.attempts(url)),
                reason=f"status {reply.status}, worth one more try",
            )
        if reply.unchanged:
            return Outcome(Result.UNCHANGED, url, response=reply)
        if not reply.ok:
            return Outcome(Result.FAILED, url, response=reply, reason=f"status {reply.status}")
        capture = capture_of(reply, channel.slug, url, at, profile_key, licence_serial)
        return Outcome(Result.FETCHED, url, response=reply, capture=capture)

    def _turn_away(self, slug: str, url: str, reply: Response, at: dt.datetime) -> Outcome:
        why = f"{slug} turned us away with a {reply.status} and is left alone for this run"
        self._turned_away[slug] = why
        wait = retry_after_ms(reply.headers.get("retry-after"), at)
        resume = at + dt.timedelta(milliseconds=wait) if wait is not None else None
        return Outcome(Result.REFUSED, url, wait_ms=wait or 0, resume_at=resume, reason=why)

    @staticmethod
    def _held(url: str, grant: Grant) -> Outcome:
        reasons = {
            Hold.CRAWL_DELAY: "the crawl delay has not run out",
            Hold.COURTESY_WINDOW: "the courtesy window is shut",
            Hold.DAILY_CEILING: "the daily ceiling for this channel is spent",
        }
        return Outcome(
            Result.HELD,
            url,
            wait_ms=grant.wait_ms,
            resume_at=grant.resume_at,
            reason=reasons[grant.hold],
        )
