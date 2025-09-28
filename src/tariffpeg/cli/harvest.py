"""Commands for planning and running a harvest."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, refusals
from tariffpeg.errors import Invalid
from tariffpeg.fetch.bundle import load as load_bundle
from tariffpeg.fetch.live import LiveTransport
from tariffpeg.fetch.transport import Transport
from tariffpeg.harvest.runner import Runner
from tariffpeg.harvest.session import Session
from tariffpeg.model.period import StayMonth, parse_stay_month
from tariffpeg.parse.drift import DriftWatch
from tariffpeg.parse.loader import by_channel
from tariffpeg.parse.loader import load as load_profiles
from tariffpeg.report.rows import Column

PLAN_COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("channel", "channel"),
    Column("pages", "pages", numeric=True),
    Column("reason", "why"),
)
RUN_COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("channel", "channel"),
    Column("pages", "pages", numeric=True),
    Column("new", "new", numeric=True),
    Column("seen", "seen", numeric=True),
    Column("stopped", "stopped because"),
)


def month_or_now(written: str, ctx: Context) -> StayMonth:
    """Return the month a caller named, or the one the clock is in."""
    if not written:
        return StayMonth.of(ctx.clock.now().date())
    return parse_stay_month(written)


@click.group(name="harvest")
def harvest_group() -> None:
    """Plan and run the reading of the channels."""


@harvest_group.command(name="plan")
@click.option("--at", "at", default="", help="The month to measure the sample at.")
@click.option("--on", "on", type=click.DateTime(["%Y-%m-%d"]), default=None)
@click.option("--skipped", is_flag=True, help="Also say what was left out and why.")
@click.pass_obj
def plan_command(ctx: Context, at: str, on: dt.datetime | None, skipped: bool) -> None:
    """Say where the next harvest would go."""
    with refusals():
        month = month_or_now(at, ctx)
        day = on.date() if on else ctx.clock.now().date()
        plan = service.plan(ctx.store(), month, day)
    rows = [
        {
            "licence": stop.licence_serial,
            "channel": stop.channel,
            "pages": stop.pages,
            "reason": stop.reason,
        }
        for stop in plan.stops
    ]
    ctx.emit(rows, PLAN_COLUMNS)
    if skipped:
        ctx.say("", *plan.skipped)


@harvest_group.command(name="run")
@click.option("--profiles", "profiles_path", required=True, type=click.Path(path_type=Path))
@click.option(
    "--bundle",
    "bundle_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Read from a recorded bundle instead of the network.",
)
@click.option("--live", is_flag=True, help="Actually reach the channels.")
@click.option("--at", "at", default="", help="The month to measure the sample at.")
@click.option("--on", "on", type=click.DateTime(["%Y-%m-%d"]), default=None)
@click.option("--problems", is_flag=True, help="Also print what each page could not read.")
@click.pass_obj
def run_command(
    ctx: Context,
    profiles_path: Path,
    bundle_path: Path | None,
    live: bool,
    at: str,
    on: dt.datetime | None,
    problems: bool,
) -> None:
    """Read the channels and put what comes back into the store."""
    with refusals():
        transport = _transport(bundle_path, live)
        profiles = by_channel(load_profiles(profiles_path))
        month = month_or_now(at, ctx)
        day = on.date() if on else ctx.clock.now().date()
        store = ctx.store()
        plan = service.plan(store, month, day)
        runner = Runner(
            store,
            Session(transport),
            service.channels(store),
            profiles,
            ctx.clock,
            DriftWatch(),
        )
        report = runner.run(plan)
    rows = [
        {
            "licence": stop.licence_serial,
            "channel": stop.channel,
            "pages": stop.pages_read,
            "new": stop.reviews_new,
            "seen": stop.reviews_seen,
            "stopped": stop.stopped_because,
        }
        for stop in report.stops
    ]
    ctx.emit(rows, RUN_COLUMNS)
    ctx.say("", f"{report.pages_read} pages read, {report.reviews_new} reviews added")
    if problems:
        ctx.say(*report.problems())


def _transport(bundle_path: Path | None, live: bool) -> Transport:
    if bundle_path is not None and live:
        raise Invalid("bundle", str(bundle_path), "read from a bundle or the network, not both")
    if bundle_path is not None:
        return load_bundle(bundle_path)
    if live:
        return LiveTransport()
    raise Invalid("transport", "none", "say --bundle to replay or --live to reach the channels")
