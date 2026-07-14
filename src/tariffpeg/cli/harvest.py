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
from tariffpeg.model.profile import Profile
from tariffpeg.parse.drift import DriftWatch
from tariffpeg.parse.loader import by_channel
from tariffpeg.parse.loader import load as load_profiles
from tariffpeg.report.rows import Column
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.profiles import ProfileStore

PLAN_COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("channel", "channel"),
    Column("pages", "pages", numeric=True),
    Column("reason", "why"),
)
BUDGET_COLUMNS = (
    Column("channel", "channel"),
    Column("ceiling", "a day", numeric=True),
    Column("spent", "spent", numeric=True),
    Column("wanted", "wanted", numeric=True),
    Column("granted", "fits", numeric=True),
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
@click.option(
    "--on",
    "on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day the harvest is being run on.",
)
@click.option("--licence", "ref", default="", help="Only this licence.")
@click.option("--channel", default="", help="Only this channel.")
@click.option("--skipped", is_flag=True, help="Also say what was left out and why.")
@click.option(
    "--within-budget",
    "within_budget",
    is_flag=True,
    help="Cut the plan down to what the channels will allow today.",
)
@click.pass_obj
def plan_command(
    ctx: Context,
    at: str,
    on: dt.datetime | None,
    ref: str,
    channel: str,
    skipped: bool,
    within_budget: bool,
) -> None:
    """Say where the next harvest would go."""
    with refusals():
        month = month_or_now(at, ctx)
        day = on.date() if on else ctx.clock.now().date()
        plan = service.plan(ctx.store(), month, day)
        serial = LicenceStore(ctx.store()).by_ref(ref).serial if ref else 0
        if serial or channel:
            plan = plan.narrowed(serial, channel)
        if within_budget:
            plan = service.affordable(ctx.store(), plan, day)
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


@harvest_group.command(name="budget")
@click.option("--at", "at", default="", help="The month to measure the sample at.")
@click.option(
    "--on",
    "on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day the harvest is being run on.",
)
@click.pass_obj
def budget_command(ctx: Context, at: str, on: dt.datetime | None) -> None:
    """Say what the next harvest would cost each channel today."""
    with refusals():
        day = on.date() if on else ctx.clock.now().date()
        found = service.budget(
            ctx.store(), service.plan(ctx.store(), month_or_now(at, ctx), day), day
        )
    if not found.allowances:
        ctx.say("the next harvest asks nothing of any channel")
        return
    rows = [
        {
            "channel": allowance.channel,
            "ceiling": allowance.ceiling,
            "spent": allowance.spent,
            "wanted": allowance.wanted,
            "granted": allowance.granted,
        }
        for allowance in found.allowances
    ]
    ctx.emit(rows, BUDGET_COLUMNS)
    if found.fits:
        ctx.say("", "the whole plan fits inside today")
        return
    ctx.say("", *found.lines())


@harvest_group.command(name="run")
@click.option(
    "--profiles",
    "profiles_path",
    type=click.Path(path_type=Path),
    default=None,
    help="A profile file to read, instead of the versions in the store.",
)
@click.option(
    "--bundle",
    "bundle_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Read from a recorded bundle instead of the network.",
)
@click.option("--live", is_flag=True, help="Actually reach the channels.")
@click.option("--at", "at", default="", help="The month to measure the sample at.")
@click.option(
    "--on",
    "on",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day the harvest is being run on.",
)
@click.option("--licence", "ref", default="", help="Only this licence.")
@click.option("--channel", default="", help="Only this channel.")
@click.option("--problems", is_flag=True, help="Also print what each page could not read.")
@click.option(
    "--within-budget",
    "within_budget",
    is_flag=True,
    help="Cut the run down to what the channels will allow today.",
)
@click.pass_obj
def run_command(
    ctx: Context,
    profiles_path: Path | None,
    bundle_path: Path | None,
    live: bool,
    at: str,
    on: dt.datetime | None,
    ref: str,
    channel: str,
    problems: bool,
    within_budget: bool,
) -> None:
    """Read the channels and put what comes back into the store."""
    with refusals():
        transport = transport_for(bundle_path, live)
        profiles = _profiles(ctx, profiles_path)
        month = month_or_now(at, ctx)
        day = on.date() if on else ctx.clock.now().date()
        store = ctx.store()
        plan = service.plan(store, month, day)
        serial = LicenceStore(store).by_ref(ref).serial if ref else 0
        if serial or channel:
            plan = plan.narrowed(serial, channel)
        if within_budget:
            plan = service.affordable(store, plan, day)
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


def transport_for(bundle_path: Path | None, live: bool) -> Transport:
    """Return the transport a command was told to use, or refuse to guess.

    Neither flag means no transport. Reaching the network because nobody said
    not to is the one thing this package will not do.
    """
    if bundle_path is not None and live:
        raise Invalid("bundle", str(bundle_path), "read from a bundle or the network, not both")
    if bundle_path is not None:
        return load_bundle(bundle_path)
    if live:
        return LiveTransport()
    raise Invalid("transport", "none", "say --bundle to replay or --live to reach the channels")


def _profiles(ctx: Context, path: Path | None) -> dict[str, Profile]:
    """Return the profiles a run reads with, from a file or from the store."""
    if path is not None:
        return by_channel(load_profiles(path))
    store = ProfileStore(ctx.store())
    found = store.live_by_channel(list(service.channels(ctx.store())))
    if not found:
        raise Invalid("profiles", "none", "no profile is registered, say --profiles to read a file")
    return found
