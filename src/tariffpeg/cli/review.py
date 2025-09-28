"""Commands for the reviews the unit holds."""

from __future__ import annotations

import click

from tariffpeg.cli.context import Context, refusals
from tariffpeg.errors import NotFound
from tariffpeg.model.capture import Capture
from tariffpeg.model.period import Season
from tariffpeg.model.review import Review
from tariffpeg.report.rows import Column
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.reviews import ReviewStore

COLUMNS = (
    Column("key", "review"),
    Column("stay", "stay"),
    Column("season", "season"),
    Column("points", "points", numeric=True),
    Column("raw", "as printed"),
    Column("words", "words", numeric=True),
    Column("title", "title"),
)


def as_row(review: Review) -> dict[str, object]:
    """Return the row the listing prints for a review."""
    return {
        "key": review.key,
        "stay": str(review.stay),
        "season": str(review.season()),
        "points": review.unit_points,
        "raw": review.raw_score,
        "words": review.words(),
        "title": review.title,
    }


@click.group(name="review")
def review_group() -> None:
    """Look at the reviews the unit is holding."""


@review_group.command(name="list")
@click.option("--licence", "ref", default="", help="Only this licence.")
@click.option("--channel", default="", help="Only this channel.")
@click.option("--season", default="", help="Only stays in this season.")
@click.pass_obj
def list_command(ctx: Context, ref: str, channel: str, season: str) -> None:
    """List the reviews held."""
    store = ReviewStore(ctx.store())
    with refusals():
        if ref:
            serial = LicenceStore(ctx.store()).by_ref(ref).serial
            held = store.for_licence(serial)
        elif channel:
            held = store.for_channel(channel)
        else:
            held = tuple(
                review
                for licence in LicenceStore(ctx.store()).all()
                for review in store.for_licence(licence.serial)
            )
        if season:
            wanted = Season(season)
            held = tuple(review for review in held if review.season() is wanted)
    ctx.emit([as_row(review) for review in held], COLUMNS)


@review_group.command(name="show")
@click.argument("key")
@click.pass_obj
def show_command(ctx: Context, key: str) -> None:
    """Print one review and the capture behind it."""
    with refusals():
        review = ReviewStore(ctx.store()).get(key)
        first_seen = ReviewStore(ctx.store()).first_seen(key)
        capture = _capture(ctx, review)
    ctx.say(
        f"{review.key} against licence {review.licence_serial}",
        f"stay {review.stay} ({review.season()}), {review.unit_points} points"
        f" from {review.raw_score} on the {review.channel} dial",
        f"read by profile {review.profile_key}, first held {first_seen.date()}",
        f"language {review.language}, room class {review.room_class or 'not given'}",
        "",
        review.title or "(no title)",
        review.quote(2000),
        "",
    )
    if review.has_response():
        ctx.say("the operator replied:", review.operator_response, "")
    if capture is None:
        ctx.say(f"capture {review.capture_digest}, which is not on file")
        return
    ctx.say(
        f"capture {capture.digest}",
        f"{capture.final_url} served {capture.fetched_at.isoformat()}",
        f"{capture.byte_count} bytes, status {capture.status}",
    )


def _capture(ctx: Context, review: Review) -> Capture | None:
    try:
        return CaptureStore(ctx.store()).get(review.capture_digest)
    except NotFound:
        return None
