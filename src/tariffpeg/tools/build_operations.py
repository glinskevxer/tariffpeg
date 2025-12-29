"""Write the runbook out of the numbers the code actually uses.

Every figure in here is read off a constant. A runbook that quotes a threshold
somebody changed two releases ago is worse than no runbook, because the person
reading it at seven in the morning believes it.
"""

from __future__ import annotations

import sys

from tariffpeg.claims.rules import MAX_STRENGTH
from tariffpeg.cli.context import EXIT_CODES
from tariffpeg.dedupe.syndication import DEFAULT_RULES
from tariffpeg.harvest.plan import REVIEWS_A_PAGE
from tariffpeg.model.listing import CONFIRMATION_MONTHS
from tariffpeg.model.review import SUBSTANTIAL_WORDS
from tariffpeg.parse.drift import DriftWatch
from tariffpeg.sample.regime import PUBLISHED as REGIME
from tariffpeg.tools.document import render, run, table
from tariffpeg.triage.disposition import PUBLISHED as BANDS
from tariffpeg.triage.remediation import BEFORE_THE_WORK
from tariffpeg.triage.schedule import NOTICE_DAYS, TARGET_DAYS
from tariffpeg.triage.weight import FLOOR, HALF_LIFE_MONTHS

NAME = "build_operations"
DOCUMENT = "operations.md"


def _harvest() -> list[str]:
    watch = DriftWatch()
    return [
        "## Reading the channels",
        "",
        "The robots file is read once a run. A four oh four forbids nothing and"
        " anything else that is not a page forbids everything.",
        "",
        f"A review page is assumed to carry {REVIEWS_A_PAGE} reviews when working out"
        " how many pages a shortfall is worth.",
        "",
        f"A listing is reconfirmed every {CONFIRMATION_MONTHS} months. A stale one is"
        " skipped and named in the plan.",
        "",
        f"A profile is called stale after {watch.run_before_stale} pages in a row give"
        f" nothing up, and watched when more than {watch.drop_rate_for_watch:.0%} of the"
        f" blocks across the last {watch.window} pages were dropped.",
        "",
    ]


def _sample() -> list[str]:
    rows = [
        [str(season), str(quota), str(REGIME.base[season])] for season, quota in REGIME.base.items()
    ]
    return [
        "## The sample",
        "",
        f"Regime version {REGIME.version}. The window is the last"
        f" {REGIME.lookback_months} months and at least"
        f" {REGIME.minimum_channels} independent channels are wanted.",
        "",
        *table(["season", "base quota", "before the multipliers"], rows),
        "",
        "The band and the size of the premises multiply the base. A season the"
        " operator is shut for is not sampled at all.",
        "",
        f"A review of fewer than {SUBSTANTIAL_WORDS} words counts towards the sample"
        " and never carries an assertion.",
        "",
        f"Two reviews are the same review above {DEFAULT_RULES.same_threshold:.0%}"
        f" overlap and worth looking at above {DEFAULT_RULES.likely_threshold:.0%}.",
        "",
    ]


def _triage() -> list[str]:
    half_lives = [[str(kind), f"{months} months"] for kind, months in HALF_LIFE_MONTHS.items()]
    bands = [
        ["desk enquiry", f"{BANDS.desk:g}", "-"],
        ["re-inspection", f"{BANDS.reinspection:g}", f"{BANDS.access_reinspection:g}"],
        ["urgent re-inspection", f"{BANDS.urgent:g}", f"{BANDS.access_urgent:g}"],
    ]
    return [
        "## Weighing what was found",
        "",
        f"A rule weighs one to {MAX_STRENGTH}. Weight halves over the half life of"
        f" its kind and never falls below {FLOOR:.0%} of what it started at.",
        "",
        *table(["kind", "half life"], half_lives),
        "",
        "## What happens next",
        "",
        *table(["disposition", "score", "access score"], bands),
        "",
        "A sample that is not complete holds the disposition at a desk enquiry"
        " however heavy the evidence is.",
        "",
        f"An accepted remediation notice cuts a structural finding from before the"
        f" work to {BEFORE_THE_WORK[True]:.0%} and a transient one to"
        f" {BEFORE_THE_WORK[False]:.0%}.",
        "",
    ]


def _visits() -> list[str]:
    rows = [[str(kind), f"{days} working days"] for kind, days in TARGET_DAYS.items()]
    return [
        "## Sending somebody out",
        "",
        f"A visit lands at least {NOTICE_DAYS} working days after the decision, inside"
        " the licence period, and never in a month the operator says they are shut.",
        "",
        *table(["disposition", "target"], rows),
        "",
    ]


def _exits() -> list[str]:
    rows = [[str(code), name] for name, code in sorted(EXIT_CODES.items(), key=lambda p: p[1])]
    return ["## What an exit code means", "", *table(["code", "why"], rows), ""]


def body() -> list[str]:
    """Return the lines of the runbook."""
    return [*_harvest(), *_sample(), *_triage(), *_visits(), *_exits()]


def text() -> str:
    """Return the whole runbook."""
    return render(NAME, "Operations", body())


def main() -> int:
    """Write the document, or check it, and return an exit code."""
    return run(NAME, DOCUMENT, text())


if __name__ == "__main__":
    sys.exit(main())
