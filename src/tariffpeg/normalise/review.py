"""Turning what came off a page into a review the store will accept.

Nothing here raises. A page with forty reviews on it where one has a score the
channel has never printed before should give up thirty nine reviews and one
line saying what happened to the fortieth. Raising loses the other thirty nine.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from tariffpeg.errors import Invalid
from tariffpeg.ids import normalise_slug
from tariffpeg.model.channel import Channel
from tariffpeg.model.period import StayMonth, parse_stay_month
from tariffpeg.model.review import Review
from tariffpeg.normalise.redact import redact, redact_name
from tariffpeg.parse.extract import RawReview

DATE_SHAPES = ("%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y")
"""The shapes channels print a submission date in."""

_TAG = re.compile(r"^[a-z]{2,3}")


@dataclass(frozen=True, slots=True)
class Normalised:
    """One attempt at turning a raw review into a real one."""

    review: Review | None = None
    problems: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Return whether a review came out of it."""
        return self.review is not None


def parse_submitted(text: str) -> dt.date | None:
    """Read a submission date, or return nothing if it is not a shape we know."""
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return None
    for shape in DATE_SHAPES:
        try:
            return dt.datetime.strptime(cleaned, shape).date()
        except ValueError:
            continue
    return None


def normalise_language(text: str, fallback: str = "en") -> str:
    """Return the language tag reduced to its first subtag."""
    match = _TAG.match(text.strip().lower())
    return match.group(0) if match else fallback


def normalise_room_class(text: str) -> str:
    """Return the room class as a slug, or nothing if it will not become one."""
    if not text.strip():
        return ""
    try:
        return normalise_slug(text)
    except ValueError:
        return ""


def normalise(
    raw: RawReview,
    channel: Channel,
    licence_serial: int,
    capture_digest: str,
) -> Normalised:
    """Turn one raw review into a real one, or say why it could not be."""
    problems: list[str] = []
    where = f"{channel.slug} block {raw.position}"

    raw_score = raw.get("score")
    try:
        tenths = channel.scale.parse(raw_score)
        unit_points = channel.scale.normalise(tenths)
    except Invalid as err:
        return Normalised(problems=(f"{where}: {err.reason}",))

    stay = _stay_month(raw, problems, where)
    if stay is None:
        return Normalised(problems=tuple(problems))

    reviewer = raw.get("reviewer")
    cleaned = redact(raw.get("body"), reviewer)
    if cleaned.changed:
        problems.append(f"{where}: {cleaned.summary()} from the body")

    try:
        review = Review(
            channel=channel.slug,
            channel_review_id=raw.get("channel_review_id"),
            licence_serial=licence_serial,
            stay=stay,
            unit_points=unit_points,
            raw_score=raw_score,
            body=cleaned.text,
            capture_digest=capture_digest,
            profile_key=raw.profile_key,
            title=redact(raw.get("title"), reviewer).text,
            reviewer_initials=redact_name(reviewer),
            room_class=normalise_room_class(raw.get("room_class")),
            language=normalise_language(raw.get("language"), channel.locale),
            submitted=parse_submitted(raw.get("submitted")),
            operator_response=redact(raw.get("response")).text,
        )
    except Invalid as err:
        return Normalised(problems=(*problems, f"{where}: {err.reason}"))
    return Normalised(review, tuple(problems))


def _stay_month(raw: RawReview, problems: list[str], where: str) -> StayMonth | None:
    written = raw.get("stay_month")
    if written:
        try:
            return parse_stay_month(written)
        except Invalid as err:
            problems.append(f"{where}: {err.reason}")
    submitted = parse_submitted(raw.get("submitted"))
    if submitted is not None:
        problems.append(f"{where}: the stay month was taken from the submission date")
        return StayMonth.of(submitted)
    problems.append(f"{where}: there is no stay month and no submission date to fall back on")
    return None
