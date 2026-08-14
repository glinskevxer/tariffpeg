"""Commands for deciding what happens to a licence."""

from __future__ import annotations

import datetime as dt

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, pack_asked_for, pack_option, refusals
from tariffpeg.cli.harvest import month_or_now
from tariffpeg.model.determination import Determination, movement, unexplained
from tariffpeg.model.outcome import Disposition
from tariffpeg.report.explanation import explain
from tariffpeg.report.locality import COLUMNS as PLACE_COLUMNS
from tariffpeg.report.locality import unsampled
from tariffpeg.report.movement import COLUMNS as MOVEMENT_COLUMNS
from tariffpeg.report.rows import Column
from tariffpeg.report.summary import COLUMNS as RETURN_COLUMNS
from tariffpeg.report.workload import COLUMNS as WORKLOAD_COLUMNS
from tariffpeg.store.licences import LicenceStore
from tariffpeg.triage.schedule import Booking, Diary

DECISION_COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("name", "trading name"),
    Column("disposition", "disposition"),
    Column("score", "score", numeric=True),
    Column("access", "access", numeric=True),
    Column("held", "held back"),
)
FINDING_COLUMNS = (
    Column("claim", "particular"),
    Column("declared", "declared"),
    Column("score", "score", numeric=True),
    Column("voices", "voices", numeric=True),
    Column("channels", "channels"),
)
MINUTE_COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("month", "month"),
    Column("disposition", "disposition"),
    Column("score", "score", numeric=True),
    Column("pack", "pack", numeric=True),
    Column("officer", "minuted by"),
    Column("moved", "against the last one"),
)
VISIT_COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("inspector", "inspector"),
    Column("day", "day"),
    Column("disposition", "why"),
    Column("late", "late"),
)


@click.group(name="triage")
def triage_group() -> None:
    """Decide what happens to the licences."""


@triage_group.command(name="list")
@click.option("--at", "at", default="", help="The month to decide at.")
@click.option("--needing-a-visit", is_flag=True, help="Only the ones that send somebody out.")
@click.option("--locality", default="", help="Only the premises in this place.")
@click.option(
    "--disposition",
    default=None,
    type=click.Choice([str(item) for item in Disposition]),
    help="Only the licences that came out at this disposition.",
)
@pack_option
@click.pass_obj
def list_command(
    ctx: Context,
    at: str,
    needing_a_visit: bool,
    locality: str,
    disposition: str | None,
    pack_version: int,
) -> None:
    """List what the unit would do about every active licence."""
    store = ctx.store()
    with refusals():
        month = month_or_now(at, ctx)
        found = service.decisions(store, month, pack_asked_for(pack_version))
        wanted = LicenceStore(store).matching(locality)
        names = {licence.serial: licence.trading_name for licence in wanted}
    rows = [
        {
            "licence": decision.licence_serial,
            "name": names.get(decision.licence_serial, ""),
            "disposition": str(decision.disposition),
            "score": decision.score,
            "access": decision.access_score,
            "held": decision.capped,
        }
        for decision in found
        if decision.licence_serial in names
        and (not needing_a_visit or decision.needs_a_visit)
        and (not disposition or str(decision.disposition) == disposition)
    ]
    if not rows:
        ctx.say("nothing needs doing")
        return
    ctx.emit(rows, DECISION_COLUMNS)


@triage_group.command(name="show")
@click.argument("ref")
@click.option("--at", "at", default="", help="The month to decide at.")
@pack_option
@click.pass_obj
def show_command(ctx: Context, ref: str, at: str, pack_version: int) -> None:
    """Print the findings behind one decision."""
    with refusals():
        pack = pack_asked_for(pack_version)
        licence = LicenceStore(ctx.store()).by_ref(ref)
        month = month_or_now(at, ctx)
        file = service.case_for(ctx.store(), licence, month, pack)
    ctx.say(f"{licence.ref}  {licence.trading_name}", *file.decision.reasons, "")
    rows = [
        {
            "claim": finding.claim_key,
            "declared": finding.declared,
            "score": finding.score,
            "voices": finding.voices,
            "channels": ", ".join(finding.channels) or "none",
        }
        for finding in file.decision.findings
    ]
    if not rows:
        ctx.say("nothing was found against the particulars on this licence")
        return
    ctx.emit(rows, FINDING_COLUMNS)


def diaries_of(ctx: Context) -> list[Diary]:
    """Return a diary for each inspector the settings name."""
    return [Diary(name, ctx.settings.weekly_capacity) for name in ctx.settings.inspectors]


def visit_row(booking: Booking, late: frozenset[int]) -> dict[str, object]:
    """Return the row one booked visit prints as."""
    return {
        "licence": booking.licence_serial,
        "inspector": booking.inspector,
        "day": booking.day.isoformat(),
        "disposition": str(booking.disposition),
        "late": booking.licence_serial in late,
    }


@triage_group.command(name="schedule")
@click.option("--at", "at", default="", help="The month to decide at.")
@click.option(
    "--on",
    "on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day the decision is being made on.",
)
@pack_option
@click.pass_obj
def schedule_command(ctx: Context, at: str, on: dt.datetime | None, pack_version: int) -> None:
    """Book a visit for everything that needs one."""
    with refusals():
        booked = service.visits(
            ctx.store(),
            month_or_now(at, ctx),
            on.date() if on else ctx.clock.now().date(),
            diaries_of(ctx),
            ctx.settings.holiday_days(),
            pack_asked_for(pack_version),
        )
    if not booked.bookings:
        ctx.say("nothing needs a visit")
    else:
        ctx.emit([visit_row(item, booked.late) for item in booked.bookings], VISIT_COLUMNS)
    if booked.refusals:
        ctx.say("", *booked.refusal_lines())


@triage_group.command(name="workload")
@click.option("--at", "at", default="", help="The month to decide at.")
@click.option(
    "--on",
    "on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day the decision is being made on.",
)
@pack_option
@click.pass_obj
def workload_command(ctx: Context, at: str, on: dt.datetime | None, pack_version: int) -> None:
    """Show what a month of visits would do to each inspector's diary."""
    with refusals():
        found = service.workload(
            ctx.store(),
            month_or_now(at, ctx),
            on.date() if on else ctx.clock.now().date(),
            diaries_of(ctx),
            ctx.settings.holiday_days(),
            pack_asked_for(pack_version),
        )
    if not found.span:
        ctx.say("no visit was booked, so there is nothing to spread")
        return
    ctx.emit(found.rows(), WORKLOAD_COLUMNS)
    idle = found.idle()
    if idle:
        ctx.say("", "nothing was given to: " + ", ".join(idle))
    if found.lopsided():
        ctx.say("a week is full while somebody has nothing, so this run is worth doing again")


@triage_group.command(name="return")
@click.option("--at", "at", default="", help="The month to file the return for.")
@click.pass_obj
def return_command(ctx: Context, at: str) -> None:
    """Print the return the unit files for a month."""
    with refusals():
        month = month_or_now(at, ctx)
        filed = service.monthly_return(ctx.store(), month)
    ctx.say(f"Return for {filed.month}", "")
    ctx.emit(filed.rows(), RETURN_COLUMNS)


@triage_group.command(name="explain")
@click.argument("ref")
@click.option("--at", "at", default="", help="The month to decide at.")
@pack_option
@click.pass_obj
def explain_command(ctx: Context, ref: str, at: str, pack_version: int) -> None:
    """Print the arithmetic behind one decision, step by step."""
    with refusals():
        pack = pack_asked_for(pack_version)
        licence = LicenceStore(ctx.store()).by_ref(ref)
        file = service.case_for(ctx.store(), licence, month_or_now(at, ctx), pack)
    ctx.say(*explain(file).lines())


@triage_group.command(name="locality")
@click.option("--at", "at", default="", help="The month to decide at.")
@click.pass_obj
def locality_command(ctx: Context, at: str) -> None:
    """Print the figures broken down by where the premises are."""
    with refusals():
        places = service.localities(ctx.store(), month_or_now(at, ctx))
    if not places:
        ctx.say("no active licence is on the register")
        return
    ctx.emit([place.row() for place in places], PLACE_COLUMNS)
    nothing = unsampled(places)
    if nothing:
        ctx.say("", "nothing is properly sampled in: " + ", ".join(nothing))


def minute_row(item: Determination, moved: str) -> dict[str, object]:
    """Return the row one minute prints as."""
    return {
        "licence": item.licence_serial,
        "month": str(item.decided_at),
        "disposition": str(item.disposition),
        "score": round(item.score, 2),
        "pack": item.pack_version,
        "officer": item.officer,
        "moved": moved,
    }


@triage_group.command(name="minute")
@click.option("--at", "at", default="", help="The month to minute.")
@click.option("--officer", required=True, help="Who is taking the minute.")
@pack_option
@click.pass_obj
def minute_command(ctx: Context, at: str, officer: str, pack_version: int) -> None:
    """Write a month's decisions into the ledger."""
    store = ctx.store()
    with refusals():
        month = month_or_now(at, ctx)
        before = service.already_minuted(store, month)
        written = service.minute(store, month, officer, ctx.clock, pack_asked_for(pack_version))
    if not written:
        ctx.say(f"{month} was already minuted for every licence on the register")
        return
    ctx.emit([minute_row(item, "") for item in written], MINUTE_COLUMNS)
    if before:
        ctx.say("", f"{len(before)} licences were already minuted and were left alone")


@triage_group.command(name="ledger")
@click.argument("ref")
@click.pass_obj
def ledger_command(ctx: Context, ref: str) -> None:
    """List every minute the ledger holds about one licence."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        held = service.ledger_for(ctx.store(), licence.serial)
    if not held:
        ctx.say(f"nothing has been minuted about {licence.ref}")
        return
    rows: list[dict[str, object]] = []
    for index, item in enumerate(held):
        moved = movement(held[index - 1], item) if index else ""
        rows.append(minute_row(item, moved))
    ctx.emit(rows, MINUTE_COLUMNS)
    worrying = [
        str(item.decided_at)
        for index, item in enumerate(held)
        if index and unexplained(held[index - 1], item)
    ]
    if worrying:
        ctx.say("", "stepped back under the same pack in: " + ", ".join(worrying))


@triage_group.command(name="reconcile")
@click.option("--at", "at", default="", help="The month to read the evidence at.")
@pack_option
@click.pass_obj
def reconcile_command(ctx: Context, at: str, pack_version: int) -> None:
    """Set the ledger against what the evidence says today."""
    with refusals():
        found = service.reconciliation(
            ctx.store(), month_or_now(at, ctx), pack_asked_for(pack_version)
        )
    if not found.movements:
        ctx.say("no active licence is on the register")
        return
    ctx.emit(found.rows(), MOVEMENT_COLUMNS)
    never = found.unminuted()
    if never:
        ctx.say("", f"{len(never)} licences have never been minuted")
    if found.settled():
        ctx.say("", "every minuted licence still reads the way it was minuted")
        return
    wanting = found.wanting_a_letter()
    if wanting:
        ctx.say(
            "",
            "the operator was told something that no longer holds at: "
            + ", ".join(str(serial) for serial in wanting),
        )
