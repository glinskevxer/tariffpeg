"""Commands for the statutory sample."""

from __future__ import annotations

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, refusals
from tariffpeg.cli.harvest import month_or_now
from tariffpeg.model.period import Season
from tariffpeg.report.rows import Column
from tariffpeg.sample.regime import PUBLISHED
from tariffpeg.store.licences import LicenceStore

SEASON_COLUMNS = (
    Column("season", "season"),
    Column("wanted", "wanted", numeric=True),
    Column("held", "held", numeric=True),
    Column("short", "short", numeric=True),
)
SHORTFALL_COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("name", "trading name"),
    Column("short", "reviews short", numeric=True),
    Column("channels", "channels short", numeric=True),
    Column("worst", "worst season"),
)


@click.group(name="sample")
def sample_group() -> None:
    """Look at how far the statutory sample has got."""


@sample_group.command(name="coverage")
@click.argument("ref")
@click.option("--at", "at", default="", help="The month to measure at.")
@click.pass_obj
def coverage_command(ctx: Context, ref: str, at: str) -> None:
    """Print the coverage for one licence."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        month = month_or_now(at, ctx)
        coverage = service.coverage_for(ctx.store(), licence, month)
    ctx.say(f"{licence.ref}  {licence.trading_name}", *coverage.statement(), "")
    rows = [
        {
            "season": str(entry.season),
            "wanted": entry.wanted,
            "held": entry.held,
            "short": entry.shortfall,
        }
        for entry in coverage.seasons
    ]
    ctx.emit(rows, SEASON_COLUMNS)


@sample_group.command(name="shortfall")
@click.option("--at", "at", default="", help="The month to measure at.")
@click.pass_obj
def shortfall_command(ctx: Context, at: str) -> None:
    """List the licences that are short, worst first."""
    store = ctx.store()
    with refusals():
        month = month_or_now(at, ctx)
        found = service.coverages(store, month)
        licences = {licence.serial: licence for licence in LicenceStore(store).all()}
    short: list[tuple[int, int, str, int, str]] = []
    for serial, coverage in found.items():
        if coverage.satisfied:
            continue
        worst = coverage.short_seasons()
        short.append(
            (
                coverage.total_shortfall,
                serial,
                licences[serial].trading_name,
                coverage.channel_shortfall,
                str(worst[0]) if worst else "none",
            )
        )
    short.sort(key=lambda entry: (-entry[0], entry[1]))
    rows: list[dict[str, object]] = [
        {
            "licence": serial,
            "name": name,
            "short": total,
            "channels": channels,
            "worst": worst_season,
        }
        for total, serial, name, channels, worst_season in short
    ]
    if not rows:
        ctx.say("every active licence is properly sampled")
        return
    ctx.emit(rows, SHORTFALL_COLUMNS)


@sample_group.command(name="regime")
@click.argument("ref")
@click.pass_obj
def regime_command(ctx: Context, ref: str) -> None:
    """Print what the regime asks of one licence and why."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        wanted = PUBLISHED.require(licence)
    ctx.say(
        f"{licence.ref}  {licence.trading_name}",
        f"regime version {PUBLISHED.version}, looking back {wanted.lookback_months} months",
        f"band {licence.band()} multiplies by {PUBLISHED.band_factor(licence.band())}",
        f"size multiplies by {PUBLISHED.size_factor(int(licence.particular('let_rooms')))}",
        *wanted.explain(),
        f"{wanted.total} reviews in all",
    )
    ctx.say(
        "",
        *[
            f"{season}: open for {PUBLISHED.open_share(licence, season):.0%} of it"
            for season in Season
        ],
    )
