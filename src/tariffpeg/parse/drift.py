"""Noticing that a profile has stopped working before anybody quotes from it.

A channel that changes its templates does not send a notice. The selectors stop
matching and every property on that channel starts reporting no reviews, which
is indistinguishable from a quiet season if nothing is counting. This is the
thing that counts.

Two failures are told apart because the fix is different. Finding no review
blocks at all means the container selector is wrong. Finding blocks and getting
nothing out of them means the field selectors are wrong and the container is
still fine.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from tariffpeg.errors import Invalid
from tariffpeg.parse.extract import Extraction


class DriftState(StrEnum):
    """What the watch thinks of a profile."""

    HEALTHY = "healthy"
    WATCH = "watch"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class Reading:
    """What one page gave up, reduced to the three numbers that matter."""

    page_url: str
    blocks_seen: int
    yielded: int
    dropped: int

    @classmethod
    def of(cls, extraction: Extraction, page_url: str = "") -> Reading:
        """Reduce an extraction to a reading."""
        return cls(page_url, extraction.blocks_seen, extraction.yielded, len(extraction.dropped))


@dataclass(slots=True)
class DriftWatch:
    """Keeps the last few readings per profile and says what they add up to."""

    window: int = 6
    run_before_stale: int = 3
    drop_rate_for_watch: float = 0.5
    _readings: dict[str, deque[Reading]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.window < 1:
            raise Invalid("window", self.window, "a watch has to remember at least one reading")
        if self.run_before_stale < 1:
            raise Invalid("run_before_stale", self.run_before_stale, "a run is one reading or more")
        if self.run_before_stale > self.window:
            raise Invalid(
                "run_before_stale",
                self.run_before_stale,
                "a run longer than the window can never be reached",
            )
        if not 0 < self.drop_rate_for_watch <= 1:
            raise Invalid("drop_rate_for_watch", self.drop_rate_for_watch, "a rate is above nought")

    def record(self, profile_key: str, reading: Reading) -> None:
        """Note what a page gave up under this profile."""
        if profile_key not in self._readings:
            self._readings[profile_key] = deque(maxlen=self.window)
        self._readings[profile_key].append(reading)

    def readings(self, profile_key: str) -> tuple[Reading, ...]:
        """Return the readings kept for a profile, oldest first."""
        return tuple(self._readings.get(profile_key, ()))

    def watched(self) -> tuple[str, ...]:
        """Return the profiles this watch is holding readings for."""
        return tuple(sorted(self._readings))

    def forget(self, profile_key: str) -> None:
        """Drop the readings for a profile, which is what a new version does."""
        self._readings.pop(profile_key, None)

    def state(self, profile_key: str) -> DriftState:
        """Return what the readings for this profile add up to."""
        kept = self.readings(profile_key)
        if not kept:
            return DriftState.HEALTHY
        run = kept[-self.run_before_stale :]
        if len(run) >= self.run_before_stale:
            if all(reading.blocks_seen == 0 for reading in run):
                return DriftState.STALE
            if all(reading.blocks_seen and reading.yielded == 0 for reading in run):
                return DriftState.STALE
        seen = sum(reading.blocks_seen for reading in kept)
        dropped = sum(reading.dropped for reading in kept)
        if seen and dropped / seen >= self.drop_rate_for_watch:
            return DriftState.WATCH
        return DriftState.HEALTHY

    def reason(self, profile_key: str) -> str:
        """Return one line saying why a profile is in the state it is in."""
        kept = self.readings(profile_key)
        state = self.state(profile_key)
        if state is DriftState.HEALTHY:
            return ""
        run = kept[-self.run_before_stale :]
        if state is DriftState.STALE and all(reading.blocks_seen == 0 for reading in run):
            return (
                f"{len(run)} pages in a row with no review blocks, the container selector is gone"
            )
        if state is DriftState.STALE:
            return f"{len(run)} pages in a row where no block gave up a required field"
        seen = sum(reading.blocks_seen for reading in kept)
        dropped = sum(reading.dropped for reading in kept)
        return f"{dropped} of {seen} blocks dropped across the last {len(kept)} pages"

    def problems(self) -> tuple[str, ...]:
        """Return one line for every profile that is not healthy."""
        lines: list[str] = []
        for key in self.watched():
            state = self.state(key)
            if state is not DriftState.HEALTHY:
                lines.append(f"{key} is {state}: {self.reason(key)}")
        return tuple(lines)
