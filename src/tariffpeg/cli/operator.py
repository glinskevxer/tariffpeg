"""Commands for the operator register."""

from __future__ import annotations

import datetime as dt

import click

from tariffpeg.cli.context import Context, refusals
from tariffpeg.model.operator import Operator
from tariffpeg.report.rows import Column
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.operators import OperatorStore

COLUMNS = (
    Column("ref", "reference"),
    Column("name", "name"),
    Column("contact", "write to"),
    Column("email", "address"),
    Column("licences", "licences", numeric=True),
)
LICENCE_COLUMNS = (
    Column("ref", "licence"),
    Column("name", "trading name"),
    Column("locality", "locality"),
    Column("status", "status"),
)


@click.group(name="operator")
def operator_group() -> None:
    """Look after the register of who holds the licences."""


@operator_group.command(name="add")
@click.argument("ref")
@click.option("--name", required=True, help="The name on the licence.")
@click.option("--contact", required=True, help="The person a letter is addressed to.")
@click.option("--email", required=True, help="Where a letter goes.")
@click.option("--address", required=True, help="The address on the register.")
@click.option(
    "--registered",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day they joined the register, today if left out.",
)
@click.option("--note", default="", help="Anything the unit wants on the file.")
@click.pass_obj
def add_command(
    ctx: Context,
    ref: str,
    name: str,
    contact: str,
    email: str,
    address: str,
    registered: dt.datetime | None,
    note: str,
) -> None:
    """Put an operator on the register."""
    with refusals():
        operator = Operator(
            ref=ref,
            name=name,
            contact_name=contact,
            email=email,
            address=address,
            registered_on=registered.date() if registered else ctx.clock.now().date(),
            note=note,
        )
        OperatorStore(ctx.store()).add(operator)
    ctx.say(f"{operator.ref} registered")


@operator_group.command(name="list")
@click.option("--holding", default=0, type=int, help="Only those holding more than this many.")
@click.pass_obj
def list_command(ctx: Context, holding: int) -> None:
    """List the operators on the register."""
    store = OperatorStore(ctx.store())
    with refusals():
        held = store.holding_more_than(holding - 1) if holding else store.all()
        rows = [
            {
                "ref": operator.ref,
                "name": operator.name,
                "contact": operator.contact_name,
                "email": operator.email,
                "licences": len(store.serials_for(operator.ref)),
            }
            for operator in held
        ]
    if not rows:
        ctx.say("nobody is on the operator register")
        return
    ctx.emit(rows, COLUMNS)


@operator_group.command(name="show")
@click.argument("ref")
@click.pass_obj
def show_command(ctx: Context, ref: str) -> None:
    """Print one operator and the licences they hold."""
    with refusals():
        operator = OperatorStore(ctx.store()).get(ref)
        held = LicenceStore(ctx.store()).for_operator(ref)
    ctx.say(
        f"{operator.ref}  {operator.name}",
        f"write to {operator.letter_to()}",
        f"{operator.email}",
        operator.address,
        f"on the register since {operator.registered_on}",
    )
    if operator.note:
        ctx.say(operator.note)
    ctx.say("")
    if not held:
        ctx.say("they hold no licences")
        return
    rows = [
        {
            "ref": licence.ref,
            "name": licence.trading_name,
            "locality": licence.locality,
            "status": str(licence.status),
        }
        for licence in held
    ]
    ctx.emit(rows, LICENCE_COLUMNS)


@operator_group.command(name="contact")
@click.argument("ref")
@click.option("--contact", required=True, help="The person a letter is addressed to.")
@click.option("--email", required=True, help="Where a letter goes.")
@click.pass_obj
def contact_command(ctx: Context, ref: str, contact: str, email: str) -> None:
    """Change who a letter to this operator is addressed to."""
    store = OperatorStore(ctx.store())
    with refusals():
        store.replace(store.get(ref).with_contact(contact, email))
    ctx.say(f"{ref} now writes to {contact}")


@operator_group.command(name="hold")
@click.argument("licence_ref")
@click.argument("operator_ref")
@click.pass_obj
def hold_command(ctx: Context, licence_ref: str, operator_ref: str) -> None:
    """Tie a licence to an operator on the register."""
    licences = LicenceStore(ctx.store())
    with refusals():
        operator = OperatorStore(ctx.store()).get(operator_ref)
        licence = licences.by_ref(licence_ref)
        licences.replace(licence.with_operator(operator.ref))
    ctx.say(f"{licence.ref} is held by {operator.ref}")


@operator_group.command(name="remove")
@click.argument("ref")
@click.confirmation_option(prompt="Take this operator off the register?")
@click.pass_obj
def remove_command(ctx: Context, ref: str) -> None:
    """Take an operator off the register, if they hold nothing."""
    with refusals():
        OperatorStore(ctx.store()).remove(ref)
    ctx.say(f"{ref} removed")
