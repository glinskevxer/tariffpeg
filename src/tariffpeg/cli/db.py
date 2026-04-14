"""Commands for the store itself."""

from __future__ import annotations

import datetime as dt

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, refusals
from tariffpeg.cli.harvest import month_or_now
from tariffpeg.report.rows import Column
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.migrations import MIGRATIONS, applied, current_version, drift, migrate
from tariffpeg.store.retention import run as run_prune
from tariffpeg.store.reviews import ReviewStore

COUNTS = (Column("what", "what"), Column("held", "held", numeric=True))
MIGRATION_COLUMNS = (
    Column("number", "number", numeric=True),
    Column("name", "name"),
    Column("state", "state"),
)


@click.group(name="db")
def db_group() -> None:
    """Look after the evidence store."""


@db_group.command(name="migrate")
@click.pass_obj
def migrate_command(ctx: Context) -> None:
    """Bring the store up to the schema this version expects."""
    with refusals():
        ran = migrate(ctx.store(), ctx.clock)
    if not ran:
        ctx.say("the store was already up to date")
        return
    ctx.say(f"applied {', '.join(str(number) for number in ran)}")


@db_group.command(name="status")
@click.pass_obj
def status_command(ctx: Context) -> None:
    """Say what the store holds."""
    store = ctx.store()
    with refusals():
        version = current_version(store)
    ctx.say(f"{store.path}, schema version {version} of {len(MIGRATIONS)}")
    ctx.emit(_counts(store), COUNTS)


@db_group.command(name="migrations")
@click.pass_obj
def migrations_command(ctx: Context) -> None:
    """List the migrations and whether they have run."""
    store = ctx.store()
    with refusals():
        record = applied(store)
    rows: list[dict[str, object]] = [
        {
            "number": migration.number,
            "name": migration.name,
            "state": "applied" if migration.number in record else "pending",
        }
        for migration in MIGRATIONS
    ]
    ctx.emit(rows, MIGRATION_COLUMNS)


@db_group.command(name="verify")
@click.pass_obj
def verify_command(ctx: Context) -> None:
    """Check the store against itself and against this version."""
    store = ctx.store()
    with refusals():
        problems = [
            *store.integrity_problems(),
            *drift(store),
            *CaptureStore(store).body_problems(),
        ]
    if not problems:
        ctx.say("the store verifies")
        return
    for problem in problems:
        ctx.say(problem)
    raise click.exceptions.Exit(5)


def _counts(store: Database) -> list[dict[str, object]]:
    return [
        {"what": "licences", "held": len(LicenceStore(store).all())},
        {"what": "channels", "held": len(ChannelStore(store).all())},
        {"what": "captures", "held": CaptureStore(store).count()},
        {"what": "pages kept", "held": CaptureStore(store).bodies_held()},
        {"what": "bytes kept", "held": CaptureStore(store).bytes_held()},
        {"what": "reviews", "held": _reviews(store)},
    ]


def _reviews(store: Database) -> int:
    reviews = ReviewStore(store)
    return sum(reviews.count_for(licence.serial) for licence in LicenceStore(store).all())


@db_group.command(name="prune")
@click.option(
    "--before",
    type=click.DateTime(["%Y-%m-%d"]),
    required=True,
    help="Drop page bodies fetched before this day.",
)
@click.option("--at", "at", default="", help="The month to reckon live case files at.")
@click.option("--run", "go", is_flag=True, help="Actually drop them.")
@click.pass_obj
def prune_command(ctx: Context, before: dt.datetime, at: str, go: bool) -> None:
    """Drop the page bodies nothing is relying on any more."""
    with refusals():
        plan = service.retention_plan(ctx.store(), before.date(), month_or_now(at, ctx))
    ctx.say(*plan.lines())
    if not go:
        ctx.say("nothing was dropped, say --run to do it")
        return
    with refusals():
        went = run_prune(ctx.store(), plan)
    ctx.say(f"{went} page bodies dropped")
