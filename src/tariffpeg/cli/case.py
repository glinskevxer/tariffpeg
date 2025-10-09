"""Commands for the case file."""

from __future__ import annotations

from pathlib import Path

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, refusals
from tariffpeg.cli.harvest import month_or_now
from tariffpeg.report.casefile import Quotation
from tariffpeg.report.rows import Column, as_csv
from tariffpeg.store.licences import LicenceStore

QUOTATION_COLUMNS = (
    Column("claim", "particular"),
    Column("review", "review"),
    Column("channel", "channel"),
    Column("stay", "stay"),
    Column("weight", "weight", numeric=True),
    Column("digest", "capture"),
    Column("quote", "what was said"),
)


def as_row(item: Quotation, digest_length: int) -> dict[str, object]:
    """Return the row a quotation prints as."""
    return {
        "claim": item.claim_key,
        "review": item.review_key,
        "channel": item.channel,
        "stay": str(item.stay),
        "weight": item.weight,
        "digest": item.capture_digest[:digest_length],
        "quote": item.quote,
    }


@click.group(name="case")
def case_group() -> None:
    """Build the file an inspector is handed."""


@case_group.command(name="show")
@click.argument("ref")
@click.option("--at", "at", default="", help="The month to decide at.")
@click.pass_obj
def show_command(ctx: Context, ref: str, at: str) -> None:
    """Print the whole case file."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        file = service.case_for(ctx.store(), licence, month_or_now(at, ctx))
    ctx.say(*file.lines())


@case_group.command(name="quotations")
@click.argument("ref")
@click.option("--at", "at", default="", help="The month to decide at.")
@click.pass_obj
def quotations_command(ctx: Context, ref: str, at: str) -> None:
    """List the quotations behind a case, with the captures they came from."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        file = service.case_for(ctx.store(), licence, month_or_now(at, ctx))
    if not file.quotations:
        ctx.say(f"{licence.ref} has nothing quoted against it")
        return
    ctx.emit([as_row(item, 19) for item in file.quotations], QUOTATION_COLUMNS)


@case_group.command(name="export")
@click.argument("ref")
@click.option("--to", "directory", required=True, type=click.Path(path_type=Path))
@click.option("--at", "at", default="", help="The month to decide at.")
@click.pass_obj
def export_command(ctx: Context, ref: str, directory: Path, at: str) -> None:
    """Write the case file and its quotations out as files."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        file = service.case_for(ctx.store(), licence, month_or_now(at, ctx))
    directory.mkdir(parents=True, exist_ok=True)
    document = directory / f"{licence.ref}.txt"
    document.write_text("\n".join(file.lines()) + "\n", encoding="utf-8", newline="\n")
    rows = [as_row(item, len(item.capture_digest)) for item in file.quotations]
    quotations = directory / f"{licence.ref}-quotations.csv"
    quotations.write_text(as_csv(rows, QUOTATION_COLUMNS), encoding="utf-8", newline="\n")
    ctx.say(f"wrote {document}", f"wrote {quotations}")
