"""Commands for the channel register."""

from __future__ import annotations

from pathlib import Path

import click

from tariffpeg import service
from tariffpeg.cli.context import Context, refusals
from tariffpeg.cli.harvest import month_or_now, transport_for
from tariffpeg.errors import Invalid
from tariffpeg.harvest.session import Session
from tariffpeg.model.channel import ALWAYS, Channel, CourtesyWindow, FetchPolicy, SyndicationClass
from tariffpeg.model.scale import SCALES
from tariffpeg.report.rows import Column
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.listings import ListingStore

COLUMNS = (
    Column("slug", "slug"),
    Column("name", "name"),
    Column("syndication", "carries"),
    Column("scale", "dial"),
    Column("delay", "delay ms", numeric=True),
    Column("ceiling", "a day", numeric=True),
    Column("window", "window"),
)


def parse_window(written: str) -> CourtesyWindow:
    """Read a courtesy window written as two hours with a dash between them."""
    if not written.strip():
        return ALWAYS
    start, sep, end = written.partition("-")
    if not sep:
        raise Invalid("window", written, "write it as 22-6")
    try:
        return CourtesyWindow(int(start), int(end))
    except ValueError:
        raise Invalid("window", written, "both ends of a window are whole hours") from None


def as_row(channel: Channel) -> dict[str, object]:
    """Return the row the listing prints for a channel."""
    window = channel.policy.window
    return {
        "slug": channel.slug,
        "name": channel.name,
        "syndication": str(channel.syndication),
        "scale": channel.scale_slug,
        "delay": channel.policy.crawl_delay_ms,
        "ceiling": channel.policy.daily_request_ceiling,
        "window": f"{window.open_hour}-{window.close_hour}",
    }


@click.group(name="channel")
def channel_group() -> None:
    """Look after the channels the unit reads."""


@channel_group.command(name="add")
@click.argument("slug")
@click.option("--name", required=True, help="What the channel calls itself.")
@click.option("--url", required=True, help="The https base with no trailing slash.")
@click.option(
    "--syndication",
    default="primary",
    type=click.Choice([str(c) for c in SyndicationClass]),
    help="Whether the channel collects its own reviews or reproduces them.",
)
@click.option(
    "--scale",
    default="ten-point",
    type=click.Choice(sorted(SCALES)),
    help="The published dial this channel scores on.",
)
@click.option("--delay", "delay_ms", default=2000, type=int, help="The agreed crawl delay.")
@click.option("--ceiling", default=300, type=int, help="Requests a day this channel agreed to.")
@click.option("--window", default="", help="The courtesy window, as 22-6.")
@click.option("--pages", default=8, type=int, help="Pages per property in one run.")
@click.option("--locale", default="en", help="The language the channel serves.")
@click.pass_obj
def add_command(
    ctx: Context,
    slug: str,
    name: str,
    url: str,
    syndication: str,
    scale: str,
    delay_ms: int,
    ceiling: int,
    window: str,
    pages: int,
    locale: str,
) -> None:
    """Register a channel and the terms agreed with it."""
    with refusals():
        policy = FetchPolicy(
            user_agent=ctx.settings.user_agent,
            crawl_delay_ms=delay_ms,
            daily_request_ceiling=ceiling,
            window=parse_window(window),
            max_pages_per_property=pages,
        )
        channel = Channel(
            slug=slug,
            name=name,
            base_url=url,
            syndication=SyndicationClass(syndication),
            policy=policy,
            scale_slug=scale,
            locale=locale,
        )
        ChannelStore(ctx.store()).add(channel)
    ctx.say(f"{channel.slug} registered")


@channel_group.command(name="list")
@click.option("--syndication", default="", help="Only channels of this kind.")
@click.pass_obj
def list_command(ctx: Context, syndication: str) -> None:
    """List the registered channels."""
    store = ChannelStore(ctx.store())
    with refusals():
        held = store.of_class(SyndicationClass(syndication)) if syndication else store.all()
    ctx.emit([as_row(channel) for channel in held], COLUMNS)


@channel_group.command(name="show")
@click.argument("slug")
@click.pass_obj
def show_command(ctx: Context, slug: str) -> None:
    """Print one channel and the terms agreed with it."""
    with refusals():
        channel = ChannelStore(ctx.store()).get(slug)
    policy = channel.policy
    ctx.say(
        f"{channel.slug}  {channel.name}",
        f"{channel.base_url}, {channel.syndication}, {channel.locale}",
        f"robots at {channel.robots_url()}",
        f"agent {policy.user_agent}",
        f"delay {policy.crawl_delay_ms} ms, ceiling {policy.daily_request_ceiling} a day",
        f"window {policy.window.open_hour} to {policy.window.close_hour},"
        f" {policy.max_pages_per_property} pages per property",
        f"dial {channel.scale_slug}, "
        + ", ".join(f"{a.tenths / 10:g} is {a.label}" for a in channel.scale.anchors),
    )


@channel_group.command(name="remove")
@click.argument("slug")
@click.confirmation_option(prompt="Take this channel off the register?")
@click.pass_obj
def remove_command(ctx: Context, slug: str) -> None:
    """Take a channel off the register."""
    with refusals():
        ChannelStore(ctx.store()).remove(slug)
    ctx.say(f"{slug} removed")


PROBE_COLUMNS = (
    Column("term", "term"),
    Column("agreed", "agreed with us"),
    Column("published", "published"),
    Column("inforce", "in force"),
)


@channel_group.command(name="probe")
@click.argument("slug")
@click.option(
    "--bundle",
    "bundle_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Read from a recorded bundle instead of the network.",
)
@click.option("--live", is_flag=True, help="Actually reach the channel.")
@click.pass_obj
def probe_command(ctx: Context, slug: str, bundle_path: Path | None, live: bool) -> None:
    """Read a channel robots file and set it against the terms agreed with us."""
    with refusals():
        channel = ChannelStore(ctx.store()).get(slug)
        session = Session(transport_for(bundle_path, live))
        at = ctx.clock.now()
        rules = session.robots_for(channel, at)
        agent = channel.policy.user_agent
        published = rules.crawl_delay_ms(agent)
        listings = ListingStore(ctx.store()).on_channel(slug)
    ctx.say(f"{channel.slug}  {channel.robots_url()}")
    if rules.unparseable:
        ctx.say("the channel could not serve its robots file, so nothing may be read")
    ctx.say("")
    rows = [
        {
            "term": "crawl delay in ms",
            "agreed": channel.policy.crawl_delay_ms,
            "published": "none" if published is None else published,
            "inforce": channel.policy.delay_with(published),
        },
        {
            "term": "requests a day",
            "agreed": channel.policy.daily_request_ceiling,
            "published": "none",
            "inforce": channel.policy.daily_request_ceiling,
        },
    ]
    ctx.emit(rows, PROBE_COLUMNS)
    ctx.say("")
    if rules.sitemaps:
        ctx.say("sitemaps: " + ", ".join(rules.sitemaps))
    if not listings:
        ctx.say("no listings are recorded on this channel")
        return
    ctx.say("what the robots file says about the pages we read:")
    for listing in listings:
        allowed = "allowed" if rules.allows(agent, listing.path) else "DISALLOWED"
        ctx.say(f"  {listing.licence_serial} {listing.path}: {allowed}")


CALIBRATION_COLUMNS = (
    Column("channel", "channel"),
    Column("earlier", "earlier median", numeric=True),
    Column("later", "later median", numeric=True),
    Column("moved", "moved", numeric=True),
    Column("verdict", "verdict"),
)


@channel_group.command(name="calibration")
@click.option("--at", "at", default="", help="The month to look back from.")
@click.option("--months", default=12, type=int, help="How many months each span covers.")
@click.pass_obj
def calibration_command(ctx: Context, at: str, months: int) -> None:
    """Set each channel recent scoring against the span before it."""
    with refusals():
        found = service.calibration(ctx.store(), month_or_now(at, ctx), months)
    if not found:
        ctx.say("no channels are registered")
        return
    rows = [
        {
            "channel": drift.channel,
            "earlier": drift.earlier.median_points,
            "later": drift.later.median_points,
            "moved": drift.shift,
            "verdict": str(drift.verdict),
        }
        for drift in found
    ]
    ctx.emit(rows, CALIBRATION_COLUMNS)
    ctx.say("")
    for drift in found:
        ctx.say(drift.line())
