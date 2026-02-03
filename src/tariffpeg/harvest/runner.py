"""Walking a plan and putting what comes back into the store.

The run stops at the first thing that says stop. A held request does not become
a retry loop here, because the thing holding it is a term the unit agreed to and
the right answer is to come back later rather than to keep asking. What the run
does instead is say, per stop, exactly why it got as far as it did.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field

from tariffpeg.clock import Clock
from tariffpeg.harvest.plan import Plan, Stop
from tariffpeg.harvest.session import Result, Session
from tariffpeg.model.channel import Channel
from tariffpeg.normalise.review import normalise
from tariffpeg.parse.dom import parse
from tariffpeg.parse.drift import DriftWatch, Reading
from tariffpeg.parse.extract import extract
from tariffpeg.parse.profile import Profile
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.db import Database
from tariffpeg.store.reviews import ReviewStore


@dataclass(frozen=True, slots=True)
class StopReport:
    """What came of visiting one stop."""

    licence_serial: int
    channel: str
    pages_read: int = 0
    retries: int = 0
    captures: int = 0
    reviews_seen: int = 0
    reviews_new: int = 0
    stopped_because: str = ""
    notes: tuple[str, ...] = ()

    def line(self) -> str:
        """Return the one line the harvest log prints for this stop."""
        return (
            f"{self.licence_serial} on {self.channel}: {self.pages_read} pages,"
            f" {self.reviews_new} new of {self.reviews_seen} seen, {self.stopped_because}"
        )


@dataclass(slots=True)
class RunReport:
    """What came of a whole run."""

    started_at: dt.datetime
    stops: list[StopReport] = field(default_factory=list)
    skipped: tuple[str, ...] = ()

    @property
    def pages_read(self) -> int:
        """Return how many pages the run fetched."""
        return sum(stop.pages_read for stop in self.stops)

    @property
    def reviews_new(self) -> int:
        """Return how many reviews the run added to the store."""
        return sum(stop.reviews_new for stop in self.stops)

    @property
    def captures(self) -> int:
        """Return how many captures the run recorded."""
        return sum(stop.captures for stop in self.stops)

    @property
    def retries_wanted(self) -> int:
        """Return how many stops asked to be come back to."""
        return sum(stop.retries for stop in self.stops)

    def problems(self) -> tuple[str, ...]:
        """Return every note the run raised, with its stop named."""
        lines: list[str] = []
        for stop in self.stops:
            lines.extend(f"{stop.licence_serial} on {stop.channel}: {note}" for note in stop.notes)
        return tuple(lines)

    def lines(self) -> tuple[str, ...]:
        """Return the harvest log."""
        return tuple(stop.line() for stop in self.stops)


class Runner:
    """Runs a plan against a session and writes what it gets to the store."""

    def __init__(
        self,
        db: Database,
        session: Session,
        channels: Mapping[str, Channel],
        profiles: Mapping[str, Profile],
        clock: Clock,
        watch: DriftWatch | None = None,
    ) -> None:
        self.db = db
        self.session = session
        self.channels = channels
        self.profiles = profiles
        self.clock = clock
        self.watch = watch if watch is not None else DriftWatch()
        self.captures = CaptureStore(db)
        self.reviews = ReviewStore(db)

    def run(self, plan: Plan) -> RunReport:
        """Walk every stop in the plan and return what happened."""
        report = RunReport(self.clock.now(), skipped=plan.skipped)
        for stop in plan.stops:
            report.stops.append(self._visit(stop))
        return report

    def _visit(self, stop: Stop) -> StopReport:
        channel = self.channels.get(stop.channel)
        profile = self.profiles.get(stop.channel)
        if channel is None:
            return StopReport(stop.licence_serial, stop.channel, stopped_because="no such channel")
        if profile is None:
            return StopReport(stop.licence_serial, stop.channel, stopped_because="no such profile")
        url = stop.url
        seen: set[str] = set()
        pages = 0
        captures = 0
        retries = 0
        found_reviews = 0
        added = 0
        notes: list[str] = []
        because = "read every page that was asked for"
        while pages < stop.pages and url:
            if url in seen:
                because = "the channel linked back to a page already read"
                break
            seen.add(url)
            at = self.clock.now()
            outcome = self.session.fetch(channel, url, at, profile.key(), stop.licence_serial)
            if outcome.result is Result.RETRY:
                retries += 1
                notes.append(f"{url}: {outcome.reason}, waiting {outcome.wait_ms} ms")
                because = f"{outcome.result}: {outcome.reason}"
                break
            if outcome.result is not Result.FETCHED:
                because = f"{outcome.result}: {outcome.reason}"
                break
            assert outcome.response is not None
            assert outcome.capture is not None
            pages += 1
            if self.captures.record(outcome.capture):
                captures += 1
            found = extract(profile, parse(outcome.response.text()), outcome.response.url)
            self.watch.record(profile.key(), Reading.of(found, url))
            notes.extend(found.notes)
            notes.extend(found.dropped)
            for raw in found.reviews:
                found_reviews += 1
                built = normalise(raw, channel, stop.licence_serial, outcome.capture.digest)
                notes.extend(built.problems)
                if built.review is not None and self.reviews.add(built.review, at):
                    added += 1
            url = found.next_page
            if not url:
                because = "the channel had no further pages"
        return StopReport(
            licence_serial=stop.licence_serial,
            channel=stop.channel,
            pages_read=pages,
            retries=retries,
            captures=captures,
            reviews_seen=found_reviews,
            reviews_new=added,
            stopped_because=because,
            notes=tuple(notes),
        )
