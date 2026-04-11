"""A review as the store holds it, after normalising and after redaction.

Two fields are worth pointing at. The score is kept twice, once as the channel
printed it and once on the unit scale, because a case file has to be able to
quote what the guest saw as well as what the unit made of it. And the capture
digest is on every review, so any quotation in a case file can be traced back
to the exact bytes that were served.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.ids import is_slug, review_key
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.model.redaction import is_clean

SUBSTANTIAL_WORDS = 12
"""Below this a review is a score with a few words attached. It still counts
towards the sample and it never carries an assertion on its own."""


@dataclass(frozen=True, slots=True)
class Review:
    """One guest review, normalised, redacted and tied to a capture."""

    channel: str
    channel_review_id: str
    licence_serial: int
    stay: StayMonth
    unit_points: int
    raw_score: str
    body: str
    capture_digest: str
    profile_key: str
    title: str = ""
    reviewer_initials: str = ""
    room_class: str = ""
    language: str = "en"
    submitted: dt.date | None = None
    operator_response: str = ""
    translated_from: str = ""

    def __post_init__(self) -> None:
        if not is_slug(self.channel):
            raise Invalid("channel", self.channel, "a review belongs to a channel slug")
        if not self.channel_review_id.strip():
            raise Invalid("channel_review_id", self.channel_review_id, "a review needs an id")
        if self.licence_serial < 0:
            raise Invalid("licence_serial", self.licence_serial, "a serial is not negative")
        if not 0 <= self.unit_points <= 100:
            raise Invalid("unit_points", self.unit_points, "the unit scale is nought to a hundred")
        if not self.body.strip():
            raise Invalid("body", self.body, "a review with no words in it is not evidence")
        if not self.capture_digest.startswith("sha256:"):
            raise Invalid("capture_digest", self.capture_digest, "a review names the capture")
        if not self.profile_key:
            raise Invalid(
                "profile_key", self.profile_key, "a review names the profile that read it"
            )
        if not is_clean(self.body):
            raise Invalid("body", self.body[:40], "this body still carries personal data")
        if self.room_class and not is_slug(self.room_class):
            raise Invalid("room_class", self.room_class, "a room class is a slug")

    @property
    def key(self) -> str:
        """Return the store key, which carries the channel."""
        return review_key(self.channel, self.channel_review_id)

    def words(self) -> int:
        """Return how many words the guest wrote."""
        return len(self.body.split())

    def is_substantial(self) -> bool:
        """Return whether there is enough here to carry an assertion."""
        return self.words() >= SUBSTANTIAL_WORDS

    def season(self) -> Season:
        """Return the season the stay fell in."""
        return self.stay.season()

    def age_in_months(self, at: StayMonth) -> int:
        """Return how many months old the stay is at a given month."""
        return at.months_since(self.stay)

    @property
    def is_translated(self) -> bool:
        """Return whether the channel served a translation rather than the words written.

        A translation still counts towards the sample. It carries less weight as
        evidence, and a case file that quotes one says so, because the words in
        the quotation are the words a machine chose.
        """
        return bool(self.translated_from.strip())

    def attribution(self) -> str:
        """Return the line a case file prints under a quotation."""
        if not self.is_translated:
            return f"written on {self.channel}"
        return f"translated by {self.channel} from {self.translated_from}"

    def has_response(self) -> bool:
        """Return whether the operator replied on the channel."""
        return bool(self.operator_response.strip())

    def quote(self, limit: int = 240) -> str:
        """Return the body cut to a length a case file can print.

        The cut lands on a word boundary and a cut quotation says so, because a
        quotation that has been shortened without saying it is a quotation an
        operator can object to.
        """
        body = " ".join(self.body.split())
        if len(body) <= limit:
            return body
        cut = body[:limit].rsplit(" ", 1)[0]
        return f"{cut} [...]"
