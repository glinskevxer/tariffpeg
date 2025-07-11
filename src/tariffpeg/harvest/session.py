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
from tariffpeg.fetch.live import host_of
from tariffpeg.fetch.pacer import Grant, Hold, Pacer
from tariffpeg.fetch.transport import Request, Response, Transport
from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel


class Result(StrEnum):
    """What came of asking for one page."""

    FETCHED = "fetched"
    UNCHANGED = "unchanged"
    HELD = "held"
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
        return self.result is Result.HELD


class Session:
    """One harvest run against one set of channels."""

    def __init__(self, transport: Transport, pacer: Pacer | None = None) -> None:
        self.transport = transport
        self.pacer = pacer if pacer is not None else Pacer()
        self._robots: dict[str, robots_reader.Robots] = {}

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
        if reply.unchanged:
            return Outcome(Result.UNCHANGED, url, response=reply)
        if not reply.ok:
            return Outcome(Result.FAILED, url, response=reply, reason=f"status {reply.status}")
        capture = Capture.of(reply, channel.slug, url, at, profile_key, licence_serial)
        return Outcome(Result.FETCHED, url, response=reply, capture=capture)

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
