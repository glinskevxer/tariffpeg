"""What this build is, for a bug report to quote."""

from __future__ import annotations

import platform
import sys

import click

from tariffpeg import __version__
from tariffpeg.claims.pack import PACK, published_versions
from tariffpeg.cli.context import Context
from tariffpeg.model.particulars import SPECS
from tariffpeg.report.rows import Column
from tariffpeg.store.migrations import MIGRATIONS

COLUMNS = (
    Column("fact", "fact"),
    Column("value", "value"),
)
"""The columns the build facts print as."""


def facts() -> list[dict[str, object]]:
    """Return what this build is, one row at a time.

    An operator disputing a case file gets told which version read their
    reviews, and the answer has to include the rule pack and the schema, because
    the package version on its own does not say what the reading was made with.
    """
    return [
        {"fact": "version", "value": __version__},
        {"fact": "rule pack in force", "value": PACK.version},
        {
            "fact": "rule packs readable",
            "value": ", ".join(str(number) for number in published_versions()),
        },
        {"fact": "rules", "value": len(PACK.rules)},
        {"fact": "particulars", "value": len(SPECS)},
        {"fact": "schema version", "value": len(MIGRATIONS)},
        {"fact": "python", "value": platform.python_version()},
        {"fact": "platform", "value": sys.platform},
    ]


@click.command(name="about")
@click.pass_obj
def about_command(ctx: Context) -> None:
    """Print what this build is, for a bug report to quote."""
    ctx.emit(facts(), COLUMNS)
