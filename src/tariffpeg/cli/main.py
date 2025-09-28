"""The command line entry point."""

from __future__ import annotations

from pathlib import Path

import click

from tariffpeg import __version__
from tariffpeg.cli.channel import channel_group
from tariffpeg.cli.config import config_group
from tariffpeg.cli.context import Context, settings_from
from tariffpeg.cli.db import db_group
from tariffpeg.cli.harvest import harvest_group
from tariffpeg.cli.licence import licence_group
from tariffpeg.cli.listing import listing_group
from tariffpeg.cli.review import review_group
from tariffpeg.errors import TariffpegError


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="tariffpeg")
@click.option(
    "--db",
    "database",
    type=click.Path(path_type=Path),
    default=None,
    help="The evidence store to work against.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="A settings file to read before anything else.",
)
@click.option("--csv", "as_csv", is_flag=True, help="Print rows as comma separated text.")
@click.pass_context
def main(
    ctx: click.Context,
    database: Path | None,
    config_path: Path | None,
    as_csv: bool,
) -> None:
    """Guest review evidence for an accommodation standards unit."""
    try:
        settings = settings_from(None if config_path is None else str(config_path))
    except TariffpegError as err:
        raise click.ClickException(str(err)) from err
    target = database if database is not None else Path(settings.database)
    ctx.obj = Context(database=target, settings=settings, as_csv=as_csv)
    ctx.call_on_close(ctx.obj.close)


main.add_command(channel_group)
main.add_command(config_group)
main.add_command(db_group)
main.add_command(harvest_group)
main.add_command(licence_group)
main.add_command(listing_group)
main.add_command(review_group)
