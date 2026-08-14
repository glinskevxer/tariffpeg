"""Commands for the register of licences."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from tariffpeg.cli.context import Context, refusals
from tariffpeg.errors import Invalid
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.particulars import SPECS, parse_value
from tariffpeg.normalise.register import read_text
from tariffpeg.report.rows import Column
from tariffpeg.store.licences import LicenceStore

COLUMNS = (
    Column("ref", "reference"),
    Column("name", "trading name"),
    Column("locality", "locality"),
    Column("band", "keys", numeric=True),
    Column("rooms", "rooms", numeric=True),
    Column("status", "status"),
)
PARTICULAR_COLUMNS = (
    Column("key", "particular"),
    Column("value", "value"),
    Column("label", "what it means"),
)


def parse_particulars(pairs: tuple[str, ...]) -> dict[str, bool | int]:
    """Read the key equals value pairs a caller typed in."""
    found: dict[str, bool | int] = {}
    for pair in pairs:
        key, sep, written = pair.partition("=")
        if not sep:
            raise Invalid("particular", pair, "write it as key=value")
        found[key.strip()] = parse_value(key.strip(), written)
    return found


def as_row(licence: Licence) -> dict[str, object]:
    """Return the row the listing prints for a licence."""
    return {
        "ref": licence.ref,
        "name": licence.trading_name,
        "locality": licence.locality,
        "band": licence.band(),
        "rooms": licence.particular("let_rooms"),
        "status": str(licence.status),
    }


@click.group(name="licence")
def licence_group() -> None:
    """Look after the register of licensed premises."""


@licence_group.command(name="add")
@click.argument("serial", type=int)
@click.option("--name", required=True, help="The trading name on the plaque.")
@click.option("--operator", required=True, help="Who holds the licence.")
@click.option("--locality", required=True, help="Which village or town it is in.")
@click.option(
    "--from",
    "period_start",
    required=True,
    type=click.DateTime(["%Y-%m-%d"]),
    help="The day the licence period starts.",
)
@click.option(
    "--to",
    "period_end",
    required=True,
    type=click.DateTime(["%Y-%m-%d"]),
    help="The day the licence period ends.",
)
@click.option("--closed", default="", help="Months the premises shuts, as 1,2,3.")
@click.option("--particular", "particulars", multiple=True, help="A particular, as key=value.")
@click.pass_obj
def add_command(
    ctx: Context,
    serial: int,
    name: str,
    operator: str,
    locality: str,
    period_start: dt.datetime,
    period_end: dt.datetime,
    closed: str,
    particulars: tuple[str, ...],
) -> None:
    """Put a licence on the register."""
    with refusals():
        months = frozenset(int(part) for part in closed.split(",") if part.strip())
        licence = Licence(
            serial=serial,
            trading_name=name,
            operator_name=operator,
            locality=locality,
            period_start=period_start.date(),
            period_end=period_end.date(),
            particulars=parse_particulars(particulars),
            closed_months=months,
        )
        LicenceStore(ctx.store()).add(licence)
    ctx.say(f"{licence.ref} added")


@licence_group.command(name="list")
@click.option("--locality", default="", help="Only this locality.")
@click.option("--status", default="", help="Only licences in this status.")
@click.pass_obj
def list_command(ctx: Context, locality: str, status: str) -> None:
    """List what is on the register."""
    store = LicenceStore(ctx.store())
    with refusals():
        held = store.matching(locality, LicenceStatus(status) if status else None)
    if not held:
        ctx.say("nothing on the register answers to that")
        return
    ctx.emit([as_row(licence) for licence in held], COLUMNS)


@licence_group.command(name="localities")
@click.pass_obj
def localities_command(ctx: Context) -> None:
    """List the places the register has premises in."""
    with refusals():
        found = LicenceStore(ctx.store()).localities()
    if not found:
        ctx.say("the register is empty")
        return
    ctx.say(*found)


@licence_group.command(name="show")
@click.argument("ref")
@click.pass_obj
def show_command(ctx: Context, ref: str) -> None:
    """Print one licence and everything it declares."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
    ctx.say(
        f"{licence.ref}  {licence.trading_name}, {licence.locality}",
        f"operator {licence.operator_name}",
        f"period {licence.period_start} to {licence.period_end}, {licence.status}",
        f"open in months {', '.join(str(month) for month in licence.open_months())}",
        "",
    )
    rows = [
        {
            "key": spec.key,
            "value": spec.render(licence.particular(spec.key)),
            "label": spec.label,
        }
        for spec in SPECS
        if licence.declares(spec.key)
    ]
    ctx.emit(rows, PARTICULAR_COLUMNS)


@licence_group.command(name="vary")
@click.argument("ref")
@click.option(
    "--particular",
    "particulars",
    multiple=True,
    required=True,
    help="A particular to change, as key=value.",
)
@click.pass_obj
def vary_command(ctx: Context, ref: str, particulars: tuple[str, ...]) -> None:
    """Change what a licence declares."""
    store = LicenceStore(ctx.store())
    with refusals():
        licence = store.by_ref(ref)
        for key, value in parse_particulars(particulars).items():
            licence = licence.with_particular(key, value)
        store.replace(licence)
    ctx.say(f"{licence.ref} varied")


@licence_group.command(name="status")
@click.argument("ref")
@click.argument("status")
@click.pass_obj
def status_command(ctx: Context, ref: str, status: str) -> None:
    """Move a licence into another status."""
    store = LicenceStore(ctx.store())
    with refusals():
        licence = store.by_ref(ref)
        store.replace(licence.with_status(LicenceStatus(status)))
    ctx.say(f"{licence.ref} is now {status}")


@licence_group.command(name="particulars")
@click.pass_obj
def particulars_command(ctx: Context) -> None:
    """List the particulars the licensing order recognises."""
    rows = [{"key": spec.key, "value": str(spec.kind), "label": spec.label} for spec in SPECS]
    ctx.emit(rows, PARTICULAR_COLUMNS)


@licence_group.command(name="remove")
@click.argument("ref")
@click.confirmation_option(prompt="Take this licence off the register?")
@click.pass_obj
def remove_command(ctx: Context, ref: str) -> None:
    """Take a licence off the register, reviews and all."""
    store = LicenceStore(ctx.store())
    with refusals():
        licence = store.by_ref(ref)
        store.remove(licence.serial)
    ctx.say(f"{licence.ref} removed")


@licence_group.command(name="import")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--dry-run", is_flag=True, help="Read the extract and write nothing.")
@click.option("--replace", is_flag=True, help="Write over licences already on the register.")
@click.pass_obj
def import_command(ctx: Context, path: Path, dry_run: bool, replace: bool) -> None:
    """Read a register extract and put what reads on the register."""
    with refusals():
        if not path.exists():
            raise Invalid("extract", str(path), "there is no extract here")
        reading = read_text(path.read_text(encoding="utf-8"))
    ctx.say(reading.summary())
    for problem in reading.problems:
        ctx.say(f"  {problem}")
    if dry_run:
        ctx.say("nothing was written")
        return
    store = LicenceStore(ctx.store())
    added = 0
    written = 0
    skipped = 0
    with refusals():
        for licence in reading.licences:
            if not store.exists(licence.serial):
                store.add(licence)
                added += 1
            elif replace:
                store.replace(licence)
                written += 1
            else:
                skipped += 1
    ctx.say(f"{added} added, {written} written over, {skipped} left alone")
