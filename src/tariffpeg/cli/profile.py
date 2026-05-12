"""Commands for the extraction profiles."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from tariffpeg.cli.context import Context, refusals
from tariffpeg.errors import Invalid
from tariffpeg.model.profile import Profile
from tariffpeg.parse.loader import load
from tariffpeg.parse.profile import check
from tariffpeg.report.rows import Column
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.profiles import ProfileStore

COLUMNS = (
    Column("channel", "channel"),
    Column("version", "version", numeric=True),
    Column("container", "one review sits at"),
    Column("fields", "fields", numeric=True),
    Column("state", "state"),
)
FIELD_COLUMNS = (
    Column("name", "field"),
    Column("source", "read from"),
    Column("what", "what"),
    Column("required", "required"),
)


def as_row(store: ProfileStore, profile: Profile) -> dict[str, object]:
    """Return the row the register prints for a profile."""
    retired = store.retired_on(profile.channel, profile.version)
    return {
        "channel": profile.channel,
        "version": profile.version,
        "container": profile.container,
        "fields": len(profile.fields),
        "state": f"retired {retired}" if retired else "live",
    }


@click.group(name="profile")
def profile_group() -> None:
    """Look after how each channel is read."""


@profile_group.command(name="register")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--channel", default="", help="Only register the profile for this channel.")
@click.option(
    "--on",
    "day",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="The day it starts being used, today if left out.",
)
@click.pass_obj
def register_command(ctx: Context, path: Path, channel: str, day: dt.datetime | None) -> None:
    """Read a profile file and put the versions in it into the store."""
    store = ProfileStore(ctx.store())
    with refusals():
        profiles = [item for item in load(path) if not channel or item.channel == channel]
        if not profiles:
            raise Invalid("profiles", channel or str(path), "there is nothing to register here")
        known = set(ChannelStore(ctx.store()).slugs())
        on = day.date() if day else ctx.clock.now().date()
        for item in profiles:
            if item.channel not in known:
                raise Invalid("channel", item.channel, "this channel is not on the register")
            store.register(check(item), on)
    ctx.say(f"{len(profiles)} profiles registered on {on}")


@profile_group.command(name="list")
@click.option("--channel", default="", help="Only this channel.")
@click.option("--all", "every", is_flag=True, help="Include the versions that were retired.")
@click.pass_obj
def list_command(ctx: Context, channel: str, every: bool) -> None:
    """List the profile versions the store holds."""
    store = ProfileStore(ctx.store())
    with refusals():
        slugs = [channel] if channel else list(ChannelStore(ctx.store()).slugs())
        rows: list[dict[str, object]] = []
        for slug in slugs:
            versions = store.versions(slug) if every else ()
            if every:
                rows.extend(as_row(store, store.get(slug, version)) for version in versions)
                continue
            live = store.live(slug)
            if live is not None:
                rows.append(as_row(store, live))
    if not rows:
        ctx.say("no profiles are registered")
        return
    ctx.emit(rows, COLUMNS)


@profile_group.command(name="show")
@click.argument("channel")
@click.option("--version", default=0, type=int, help="A version other than the live one.")
@click.pass_obj
def show_command(ctx: Context, channel: str, version: int) -> None:
    """Print one profile version and every field it reads."""
    store = ProfileStore(ctx.store())
    with refusals():
        profile = store.get(channel, version) if version else store.live(channel)
        if profile is None:
            raise Invalid("profile", channel, "no version is live for this channel")
        retired = store.retired_on(profile.channel, profile.version)
    ctx.say(
        f"{profile.key()}",
        f"one review sits at {profile.container}",
        f"the next page is at {profile.next_page or 'nowhere, this channel has one page'}",
        f"the structured copy is {'preferred' if profile.prefer_structured else 'a fallback'}",
        f"state {'retired ' + str(retired) if retired else 'live'}",
        "",
    )
    rows = [
        {
            "name": rule.name,
            "source": rule.source,
            "what": rule.key if rule.source == "structured" else rule.selector,
            "required": rule.required,
        }
        for rule in profile.fields
    ]
    ctx.emit(rows, FIELD_COLUMNS)
