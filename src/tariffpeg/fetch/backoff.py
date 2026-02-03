"""What to do when a channel says try again, and when to stop asking.

Two things a channel can say are not the same and were treated the same for one
release, which is how this module came to exist. A five hundred is the channel
having a bad minute and is worth one more try after a wait. A four two nine or a
four oh three is the channel telling us to stop, and trying again is not a retry,
it is ignoring what they said.

A channel that turns us away is left alone for the rest of the run. Not for a
minute, for the run: the next run reads its robots file again and starts over.
"""

from __future__ import annotations

import datetime as dt
import email.utils
from dataclasses import dataclass

from tariffpeg.errors import Invalid

TURNED_AWAY = frozenset({403, 429})
"""The statuses that mean stop rather than wait."""

WORTH_ANOTHER_TRY = frozenset({500, 502, 503, 504, 408})
"""The statuses that mean the channel is having a bad minute."""


@dataclass(frozen=True, slots=True)
class Backoff:
    """How long to wait, and how many times to bother."""

    tries: int = 2
    first_wait_ms: int = 2_000
    multiplier: int = 3
    longest_wait_ms: int = 120_000

    def __post_init__(self) -> None:
        if self.tries < 1:
            raise Invalid("tries", self.tries, "a request is tried at least once")
        if self.first_wait_ms < 1:
            raise Invalid("first_wait_ms", self.first_wait_ms, "a wait is a millisecond or more")
        if self.multiplier < 1:
            raise Invalid("multiplier", self.multiplier, "a backoff does not get shorter")
        if self.longest_wait_ms < self.first_wait_ms:
            raise Invalid(
                "longest_wait_ms",
                self.longest_wait_ms,
                "the longest wait is at least the first one",
            )

    def wait_after(self, attempt: int) -> int:
        """Return how long to wait after a given attempt, counting from one."""
        if attempt < 1:
            raise Invalid("attempt", attempt, "attempts are counted from one")
        waited: int = self.first_wait_ms * self.multiplier ** (attempt - 1)
        return min(waited, self.longest_wait_ms)

    def worth_another(self, attempt: int) -> bool:
        """Return whether a request that has been tried this often is worth retrying."""
        return attempt < self.tries


DEFAULT = Backoff()
"""What a channel gets unless the register says otherwise."""


def retry_after_ms(header: str, now: dt.datetime) -> int | None:
    """Return the wait a channel asked for, in milliseconds, or nothing.

    The header comes in two shapes and channels use both. A number of seconds,
    and an http date. A date in the past is read as no wait rather than as a
    negative one.
    """
    written = header.strip()
    if not written:
        return None
    try:
        return max(0, int(round(float(written) * 1000)))
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(written)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    return max(0, int((parsed - now).total_seconds() * 1000))
