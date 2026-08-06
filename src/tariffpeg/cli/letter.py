"""Commands for the correspondence register."""

from __future__ import annotations

import datetime as dt
import hashlib

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, pack_asked_for, pack_option, refusals
from tariffpeg.cli.harvest import month_or_now
from tariffpeg.model.letter import Letter, Sent
from tariffpeg.report.rows import Column
from tariffpeg.store.letters import LetterStore
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.operators import OperatorStore

COLUMNS = (
    Column("reference", "reference"),
    Column("licence", "licence", numeric=True),
    Column("kind", "kind"),
    Column("sent", "sent"),
    Column("due", "reply due"),
    Column("replied", "replied"),
    Column("subject", "about"),
)


def digest_of(text: str) -> str:
    """Return the digest recorded against a letter."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def as_row(letter: Letter) -> dict[str, object]:
    """Return the row the register prints for a letter."""
    return {
        "reference": letter.reference,
        "licence": letter.licence_serial,
        "kind": str(letter.kind),
        "sent": letter.sent_on.isoformat(),
        "due": letter.due_on().isoformat(),
        "replied": letter.replied_on.isoformat() if letter.replied_on else "",
        "subject": letter.subject,
    }


@click.group(name="letter")
def letter_group() -> None:
    """Look after what the unit sent and what came back."""


@letter_group.command(name="send")
@click.argument("reference")
@click.argument("licence_ref")
@click.option(
    "--kind",
    type=click.Choice([str(kind) for kind in Sent]),
    required=True,
    help="What kind of letter it is.",
)
@click.option("--subject", required=True, help="What the letter is about.")
@click.option("--body", required=True, help="The text that went out, so it can be digested.")
@click.option(
    "--on",
    "sent_on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day it went, today if left out.",
)
@click.pass_obj
def send_command(
    ctx: Context,
    reference: str,
    licence_ref: str,
    kind: str,
    subject: str,
    body: str,
    sent_on: dt.datetime | None,
) -> None:
    """Record that a letter went out to the operator of a licence."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(licence_ref)
        operator = OperatorStore(ctx.store()).get(licence.operator_ref)
        letter = Letter(
            reference=reference,
            operator_ref=operator.ref,
            licence_serial=licence.serial,
            kind=Sent(kind),
            sent_on=sent_on.date() if sent_on else ctx.clock.now().date(),
            subject=subject,
            body_digest=digest_of(body),
        )
        LetterStore(ctx.store()).add(letter)
    ctx.say(f"{letter.reference} sent to {operator.letter_to()}, reply due {letter.due_on()}")


@letter_group.command(name="reply")
@click.argument("reference")
@click.option(
    "--on",
    "day",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day the reply came, today if left out.",
)
@click.pass_obj
def reply_command(ctx: Context, reference: str, day: dt.datetime | None) -> None:
    """Record that the operator answered."""
    with refusals():
        when = day.date() if day else ctx.clock.now().date()
        answered = LetterStore(ctx.store()).record_reply(reference, when)
    late = " and it was late" if answered.answered_late() else ""
    ctx.say(f"{reference} answered on {when}{late}")


@letter_group.command(name="list")
@click.option("--licence", "ref", default="", help="Only letters about this licence.")
@click.option("--operator", "operator_ref", default="", help="Only letters to this operator.")
@click.option("--unanswered", is_flag=True, help="Only the ones nobody has answered.")
@click.pass_obj
def list_command(ctx: Context, ref: str, operator_ref: str, unanswered: bool) -> None:
    """List what has gone out."""
    store = LetterStore(ctx.store())
    with refusals():
        if ref:
            held = store.for_licence(LicenceStore(ctx.store()).by_ref(ref).serial)
        elif operator_ref:
            held = store.for_operator(operator_ref)
        else:
            held = store.unanswered() if unanswered else _everything(store)
        if unanswered:
            held = tuple(letter for letter in held if not letter.answered)
    if not held:
        ctx.say("nothing has gone out")
        return
    ctx.emit([as_row(letter) for letter in held], COLUMNS)


@letter_group.command(name="overdue")
@click.option(
    "--on",
    "day",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day to reckon from, today if left out.",
)
@click.pass_obj
def overdue_command(ctx: Context, day: dt.datetime | None) -> None:
    """List the letters nobody has answered in time."""
    with refusals():
        when = day.date() if day else ctx.clock.now().date()
        held = LetterStore(ctx.store()).overdue_on(when)
    if not held:
        ctx.say(f"every letter has been answered in time as at {when}")
        return
    ctx.emit([as_row(letter) for letter in held], COLUMNS)


def _everything(store: LetterStore) -> tuple[Letter, ...]:
    rows = store.db.conn.execute("SELECT reference FROM letter ORDER BY sent_on, reference")
    return tuple(store.get(str(row["reference"])) for row in rows.fetchall())


@letter_group.command(name="draft")
@click.argument("licence_ref")
@click.option("--at", "at", default="", help="The month to read the evidence at.")
@click.option(
    "--on",
    "on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day the letter would go out.",
)
@pack_option
@click.pass_obj
def draft_command(
    ctx: Context, licence_ref: str, at: str, on: dt.datetime | None, pack_version: int
) -> None:
    """Print the letter this licence's case file produces, without sending it."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(licence_ref)
        drafted = service.letter_draft(
            ctx.store(),
            licence,
            month_or_now(at, ctx),
            on.date() if on else ctx.clock.now().date(),
            pack_asked_for(pack_version),
        )
    ctx.say(*drafted.lines())
    ctx.say("", f"this would go as a {drafted.kind}, digest {digest_of(drafted.text())[:23]}")
