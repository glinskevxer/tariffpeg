"""Commands for the listing register."""

from __future__ import annotations

import datetime as dt

import click

from tariffpeg.cli.context import Context, refusals
from tariffpeg.model.listing import Listing
from tariffpeg.report.rows import Column
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.listings import ListingStore

COLUMNS = (
    Column("licence", "licence", numeric=True),
    Column("channel", "channel"),
    Column("path", "path"),
    Column("ref", "their reference"),
    Column("confirmed", "confirmed"),
    Column("active", "active"),
)


def as_row(listing: Listing) -> dict[str, object]:
    """Return the row the listing register prints."""
    return {
        "licence": listing.licence_serial,
        "channel": listing.channel,
        "path": listing.path,
        "ref": listing.property_ref,
        "confirmed": listing.confirmed_on.isoformat(),
        "active": listing.active,
    }


@click.group(name="listing")
def listing_group() -> None:
    """Look after which page is which premises."""


@listing_group.command(name="add")
@click.argument("ref")
@click.argument("channel")
@click.option("--path", required=True, help="The path on the channel, starting at the root.")
@click.option("--property-ref", required=True, help="How the channel numbers this property.")
@click.option(
    "--confirmed",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day somebody looked at the page, today if left out.",
)
@click.option("--note", default="", help="How the listing was confirmed.")
@click.pass_obj
def add_command(
    ctx: Context,
    ref: str,
    channel: str,
    path: str,
    property_ref: str,
    confirmed: dt.datetime | None,
    note: str,
) -> None:
    """Record which page on a channel is a licensed premises."""
    with refusals():
        licence = LicenceStore(ctx.store()).by_ref(ref)
        ChannelStore(ctx.store()).get(channel)
        day = confirmed.date() if confirmed else ctx.clock.now().date()
        listing = Listing(
            licence_serial=licence.serial,
            channel=channel,
            path=path,
            property_ref=property_ref,
            confirmed_on=day,
            note=note,
        )
        ListingStore(ctx.store()).add(listing)
    ctx.say(f"{listing.key} recorded")


@listing_group.command(name="list")
@click.option("--licence", "ref", default="", help="Only this licence.")
@click.option("--channel", default="", help="Only this channel.")
@click.option("--all", "include_retired", is_flag=True, help="Include retired listings.")
@click.pass_obj
def list_command(ctx: Context, ref: str, channel: str, include_retired: bool) -> None:
    """List what has been recorded."""
    store = ListingStore(ctx.store())
    active_only = not include_retired
    with refusals():
        if ref:
            serial = LicenceStore(ctx.store()).by_ref(ref).serial
            held = store.for_licence(serial, active_only)
        elif channel:
            held = store.on_channel(channel, active_only)
        else:
            held = tuple(
                listing
                for slug in ChannelStore(ctx.store()).slugs()
                for listing in store.on_channel(slug, active_only)
            )
    ctx.emit([as_row(listing) for listing in held], COLUMNS)


@listing_group.command(name="confirm")
@click.argument("ref")
@click.argument("channel")
@click.option(
    "--on",
    "day",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day to reckon from, today if left out.",
)
@click.pass_obj
def confirm_command(ctx: Context, ref: str, channel: str, day: dt.datetime | None) -> None:
    """Say that somebody has looked at the page and it is still the right one."""
    store = ListingStore(ctx.store())
    with refusals():
        serial = LicenceStore(ctx.store()).by_ref(ref).serial
        listing = store.get(serial, channel)
        store.replace(listing.confirmed(day.date() if day else ctx.clock.now().date()))
    ctx.say(f"{listing.key} confirmed")


@listing_group.command(name="retire")
@click.argument("ref")
@click.argument("channel")
@click.option("--why", required=True, help="Why the listing is no longer worth fetching.")
@click.pass_obj
def retire_command(ctx: Context, ref: str, channel: str, why: str) -> None:
    """Stop fetching a listing, and say why."""
    store = ListingStore(ctx.store())
    with refusals():
        serial = LicenceStore(ctx.store()).by_ref(ref).serial
        store.replace(store.get(serial, channel).retired(why))
    ctx.say(f"{serial}:{channel} retired")


@listing_group.command(name="stale")
@click.option(
    "--on",
    "day",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day to reckon from, today if left out.",
)
@click.pass_obj
def stale_command(ctx: Context, day: dt.datetime | None) -> None:
    """List the listings nobody has looked at lately."""
    with refusals():
        when = day.date() if day else ctx.clock.now().date()
        held = ListingStore(ctx.store()).stale_on(when)
    if not held:
        ctx.say(f"nothing needs checking as at {when}")
        return
    ctx.emit([as_row(listing) for listing in held], COLUMNS)
