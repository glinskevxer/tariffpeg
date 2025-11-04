"""Commands for the notices operators file."""

from __future__ import annotations

import datetime as dt

import click

from tariffpeg.cli.context import Context, refusals
from tariffpeg.model.period import parse_stay_month
from tariffpeg.model.remediation import Remediation
from tariffpeg.report.rows import Column
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.remediations import RemediationStore

COLUMNS = (
    Column("reference", "reference"),
    Column("claim", "particular"),
    Column("filed", "filed"),
    Column("effective", "work finished"),
    Column("accepted", "accepted"),
    Column("note", "note"),
)


@click.group(name="remediation")
def remediation_group() -> None:
    """Look after the notices operators file."""


@remediation_group.command(name="file")
@click.argument("ref")
@click.argument("claim")
@click.option("--reference", required=True, help="The number the notice was filed under.")
@click.option(
    "--filed",
    type=click.DateTime(["%Y-%m-%d"]),
    required=True,
    help="The day the operator filed the notice.",
)
@click.option("--effective", required=True, help="The month the work finished, as 2026-01.")
@click.option("--note", default="", help="What the operator sent with it.")
@click.pass_obj
def file_command(
    ctx: Context,
    ref: str,
    claim: str,
    reference: str,
    filed: dt.datetime,
    effective: str,
    note: str,
) -> None:
    """Take a notice on file. It is not accepted until somebody accepts it."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        notice = Remediation(
            licence_serial=licence.serial,
            claim_key=claim,
            reference=reference,
            filed_on=filed.date(),
            effective_from=parse_stay_month(effective),
            note=note,
        )
        RemediationStore(ctx.store()).add(notice)
    ctx.say(f"{notice.key} taken on file, not yet accepted")


@remediation_group.command(name="accept")
@click.argument("ref")
@click.argument("claim")
@click.argument("reference")
@click.option("--note", default="", help="What was produced in support.")
@click.pass_obj
def accept_command(ctx: Context, ref: str, claim: str, reference: str, note: str) -> None:
    """Accept a notice, which discounts the evidence from before the work."""
    store = RemediationStore(ctx.store())
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        notice = store.get(licence.serial, claim, reference)
        store.replace(notice.accept(note))
    ctx.say(f"{notice.key} accepted")


@remediation_group.command(name="refuse")
@click.argument("ref")
@click.argument("claim")
@click.argument("reference")
@click.option("--why", required=True, help="Why the notice was not accepted.")
@click.pass_obj
def refuse_command(ctx: Context, ref: str, claim: str, reference: str, why: str) -> None:
    """Refuse a notice, and record why."""
    store = RemediationStore(ctx.store())
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        notice = store.get(licence.serial, claim, reference)
        store.replace(notice.refuse(why))
    ctx.say(f"{notice.key} refused")


@remediation_group.command(name="list")
@click.argument("ref")
@click.option("--accepted-only", is_flag=True, help="Leave out anything not accepted.")
@click.pass_obj
def list_command(ctx: Context, ref: str, accepted_only: bool) -> None:
    """List the notices on file for a licence."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        held = RemediationStore(ctx.store()).for_licence(licence.serial, accepted_only)
    rows = [
        {
            "reference": notice.reference,
            "claim": notice.claim_key,
            "filed": notice.filed_on.isoformat(),
            "effective": str(notice.effective_from),
            "accepted": notice.accepted,
            "note": notice.note,
        }
        for notice in held
    ]
    if not rows:
        ctx.say(f"{licence.ref} has no notices on file")
        return
    ctx.emit(rows, COLUMNS)
