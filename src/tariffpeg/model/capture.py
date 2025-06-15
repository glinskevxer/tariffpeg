"""A capture: the record that a page was fetched, and what came back.

This is the chain of custody. Every review in the store points at the capture it
was read out of, and every capture carries the digest of the bytes that were
served, when they were served, and which url they were served from after any
redirect. An operator who disputes a quotation is answered with this record.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from tariffpeg.clock import require_utc
from tariffpeg.errors import Invalid
from tariffpeg.fetch.transport import Response
from tariffpeg.ids import is_slug


@dataclass(frozen=True, slots=True)
class Capture:
    """One fetched page, recorded so it can be answered for later."""

    digest: str
    channel: str
    url: str
    final_url: str
    status: int
    fetched_at: dt.datetime
    byte_count: int
    profile_key: str
    elapsed_ms: int = 0
    licence_serial: int | None = None
    etag: str = ""

    def __post_init__(self) -> None:
        if not self.digest.startswith("sha256:"):
            raise Invalid("digest", self.digest, "a capture is named by its content digest")
        if not is_slug(self.channel):
            raise Invalid("channel", self.channel, "a capture belongs to a channel slug")
        if not self.url.startswith("https://"):
            raise Invalid("url", self.url, "captures are of pages fetched over https")
        if not self.final_url.startswith("https://"):
            raise Invalid("final_url", self.final_url, "captures are of pages fetched over https")
        if not 100 <= self.status <= 599:
            raise Invalid("status", self.status, "this is not an http status")
        if self.byte_count < 0:
            raise Invalid("byte_count", self.byte_count, "a page cannot have negative bytes")
        if self.elapsed_ms < 0:
            raise Invalid("elapsed_ms", self.elapsed_ms, "a fetch cannot take negative time")
        require_utc(self.fetched_at, "fetched_at")

    @property
    def redirected(self) -> bool:
        """Return whether the page came from somewhere other than where we asked."""
        return self.final_url != self.url

    @property
    def usable(self) -> bool:
        """Return whether this capture carries a page worth reading."""
        return 200 <= self.status < 300 and self.byte_count > 0

    def age_at(self, at: dt.datetime) -> dt.timedelta:
        """Return how old this capture is at a given instant."""
        return require_utc(at, "at") - self.fetched_at

    @classmethod
    def of(
        cls,
        response: Response,
        channel: str,
        requested_url: str,
        fetched_at: dt.datetime,
        profile_key: str,
        licence_serial: int | None = None,
    ) -> Capture:
        """Record a response as a capture."""
        return cls(
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
