"""Commands for the store itself."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, refusals
from tariffpeg.cli.harvest import month_or_now
from tariffpeg.report.health import COLUMNS as HEALTH_COLUMNS
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


@db_group.command(name="backup")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_obj
def backup_command(ctx: Context, path: Path) -> None:
    """Copy the store to another file while it is still open."""
    store = ctx.store()
    with refusals():
        target = store.backup_to(path)
        with Database(target) as copy:
            problems = copy.integrity_problems()
    if problems:
        for problem in problems:
            ctx.say(problem)
        raise click.exceptions.Exit(5)
    ctx.say(f"copied {store.byte_size()} bytes to {target}, and it verifies")


@db_group.command(name="reclaim")
@click.pass_obj
def reclaim_command(ctx: Context) -> None:
    """Compact the store and say how much it gave back."""
    store = ctx.store()
    with refusals():
        freed = store.reclaim()
    ctx.say(f"{freed} bytes reclaimed, the store is now {store.byte_size()} bytes")


@db_group.command(name="health")
@click.option("--at", "at", default="", help="The month to read the evidence at.")
@click.option(
    "--on",
    "on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day to reckon the reply clocks from.",
)
@click.pass_obj
def health_command(ctx: Context, at: str, on: dt.datetime | None) -> None:
    """Say in one place whether the unit is keeping up.

    This is what the overnight job runs. It exits nothing when there is nothing
    to act on, one when the unit is behind, and two when the store itself cannot
    be relied on.
    """
    with refusals():
        found = service.health(
            ctx.store(),
            month_or_now(at, ctx),
            on.date() if on else ctx.clock.now().date(),
            ctx.settings.holiday_days(),
        )
    ctx.emit(found.rows(), HEALTH_COLUMNS)
    ctx.say("", found.summary())
    code = found.exit_code()
    if code:
        raise click.exceptions.Exit(code)
