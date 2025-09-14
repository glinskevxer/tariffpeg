"""Commands for the settings file."""

from __future__ import annotations

from pathlib import Path

import click

from tariffpeg.cli.context import Context, refusals
from tariffpeg.report.rows import Column
from tariffpeg.settings import DEFAULTS, describe, load

COLUMNS = (
    Column("setting", "setting"),
    Column("value", "value"),
    Column("changed", "changed"),
)


@click.group(name="config")
def config_group() -> None:
    """Look at the settings this run is using."""


@config_group.command(name="show")
@click.option("--changed-only", is_flag=True, help="Leave out anything still at its default.")
@click.pass_obj
def show_command(ctx: Context, changed_only: bool) -> None:
    """Print the settings in force."""
    rows = [dict(row) for row in describe(ctx.settings)]
    if changed_only:
        rows = [row for row in rows if row["changed"]]
    if not rows:
        ctx.say("every setting is at its default")
        return
    ctx.emit(rows, COLUMNS)


@config_group.command(name="defaults")
@click.pass_obj
def defaults_command(ctx: Context) -> None:
    """Print what the package ships with."""
    ctx.emit([dict(row) for row in describe(DEFAULTS)], COLUMNS)


@config_group.command(name="check")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_obj
def check_command(ctx: Context, path: Path) -> None:
    """Read a settings file and say whether it is usable."""
    with refusals():
        settings = load(path)
    changed = settings.changed_from_default()
    ctx.say(f"{path} reads, {len(changed)} settings changed from the default")
    for key, value in sorted(changed.items()):
        ctx.say(f"  {key} = {value}")
