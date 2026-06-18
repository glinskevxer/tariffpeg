"""Commands for deciding what happens to a licence."""

from __future__ import annotations

import datetime as dt

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, refusals
from tariffpeg.cli.harvest import month_or_now
from tariffpeg.report.explanation import explain
from tariffpeg.report.locality import COLUMNS as PLACE_COLUMNS
from tariffpeg.report.locality import unsampled
from tariffpeg.report.rows import Column
from tariffpeg.report.summary import COLUMNS as RETURN_COLUMNS
from tariffpeg.store.licences import LicenceStore
from tariffpeg.triage.disposition import Disposition
from tariffpeg.triage.schedule import Booking, Diary, Scheduler

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
@click.pass_obj
def list_command(ctx: Context, at: str, needing_a_visit: bool) -> None:
    """List what the unit would do about every active licence."""
    store = ctx.store()
    with refusals():
        month = month_or_now(at, ctx)
        found = service.decisions(store, month)
        names = {licence.serial: licence.trading_name for licence in LicenceStore(store).all()}
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
        if not needing_a_visit or decision.needs_a_visit
    ]
    if not rows:
        ctx.say("nothing needs doing")
        return
    ctx.emit(rows, DECISION_COLUMNS)


@triage_group.command(name="show")
@click.argument("ref")
@click.option("--at", "at", default="", help="The month to decide at.")
@click.pass_obj
def show_command(ctx: Context, ref: str, at: str) -> None:
    """Print the findings behind one decision."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        month = month_or_now(at, ctx)
        file = service.case_for(ctx.store(), licence, month)
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


@triage_group.command(name="schedule")
@click.option("--at", "at", default="", help="The month to decide at.")
@click.option(
    "--on",
    "on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day the decision is being made on.",
)
@click.pass_obj
def schedule_command(ctx: Context, at: str, on: dt.datetime | None) -> None:
    """Book a visit for everything that needs one."""
    store = ctx.store()
    with refusals():
        month = month_or_now(at, ctx)
        decided_on = on.date() if on else ctx.clock.now().date()
        found = service.decisions(store, month)
        licences = {licence.serial: licence for licence in LicenceStore(store).all()}
        scheduler = Scheduler(
            [Diary(name, ctx.settings.weekly_capacity) for name in ctx.settings.inspectors]
        )
        rows: list[dict[str, object]] = []
        refused: list[str] = []
        for decision in found:
            if decision.disposition in (Disposition.NO_ACTION, Disposition.DESK_ENQUIRY):
                continue
            outcome = scheduler.book(
                licences[decision.licence_serial], decision.disposition, decided_on
            )
            if isinstance(outcome, Booking):
                rows.append(
                    {
                        "licence": outcome.licence_serial,
                        "inspector": outcome.inspector,
                        "day": outcome.day.isoformat(),
                        "disposition": str(outcome.disposition),
                        "late": scheduler.overdue(outcome, decided_on),
                    }
                )
            else:
                refused.append(f"{outcome.licence_serial}: {outcome.reason}")
    if not rows:
        ctx.say("nothing needs a visit")
    else:
        ctx.emit(rows, VISIT_COLUMNS)
    if refused:
        ctx.say("", *refused)


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
@click.pass_obj
def explain_command(ctx: Context, ref: str, at: str) -> None:
    """Print the arithmetic behind one decision, step by step."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        file = service.case_for(ctx.store(), licence, month_or_now(at, ctx))
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
