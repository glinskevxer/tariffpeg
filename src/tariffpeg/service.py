"""The layer that puts the store together with the rules.

Everything below this is either a pure function or a table. This is where the
two meet, and it is deliberately thin: reading rows, calling something that
knows nothing about rows, and handing back the answer. Anything here that starts
making decisions belongs one layer down where it can be tested without a store.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from pathlib import Path

from tariffpeg.claims.pack import PACK
from tariffpeg.claims.rules import RulePack
from tariffpeg.dedupe.syndication import DEFAULT_RULES, SyndicationRules
from tariffpeg.errors import Invalid
from tariffpeg.fetch.bundle import INDEX
from tariffpeg.harvest.plan import Plan
from tariffpeg.harvest.plan import build as build_plan
from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.listing import Listing
from tariffpeg.model.period import StayMonth
from tariffpeg.report.casefile import CaseFile
from tariffpeg.report.casefile import build as build_case
from tariffpeg.report.locality import Place, by_locality
from tariffpeg.report.summary import Return, compile_return
from tariffpeg.sample.calibration import TOLERANCE, Drift, look_back
from tariffpeg.sample.coverage import Coverage, measure
from tariffpeg.sample.regime import PUBLISHED, Regime
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.listings import ListingStore
from tariffpeg.store.remediations import RemediationStore
from tariffpeg.store.retention import Prune
from tariffpeg.store.retention import plan as build_prune
from tariffpeg.store.reviews import ReviewStore
from tariffpeg.triage.disposition import Decision, Thresholds

NEWLINE = chr(10)
"""What the bundle index is written with, whatever platform writes it."""


def channels(db: Database) -> dict[str, Channel]:
    """Return every registered channel, by slug."""
    return {channel.slug: channel for channel in ChannelStore(db).all()}


def listings(db: Database) -> dict[int, list[Listing]]:
    """Return the active listings, by licence serial."""
    store = ListingStore(db)
    found: dict[int, list[Listing]] = {}
    for slug in ChannelStore(db).slugs():
        for listing in store.on_channel(slug):
            found.setdefault(listing.licence_serial, []).append(listing)
    return found


def coverage_for(
    db: Database,
    licence: Licence,
    at: StayMonth,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Coverage:
    """Return what is held for one licence against what the regime asks."""
    reviews = ReviewStore(db).for_licence(licence.serial)
    return measure(regime.require(licence), reviews, channels(db), at, rules)


def coverages(
    db: Database,
    at: StayMonth,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> dict[int, Coverage]:
    """Return the coverage for every active licence."""
    found: dict[int, Coverage] = {}
    for licence in LicenceStore(db).with_status(LicenceStatus.ACTIVE):
        found[licence.serial] = coverage_for(db, licence, at, regime, rules)
    return found


def plan(
    db: Database,
    at: StayMonth,
    on: dt.date,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Plan:
    """Return the plan for the next harvest.

    Every licence goes to the planner, not just the active ones. The planner is
    where the reasons for leaving a licence out are written down, and a licence
    filtered out before it gets there is a licence nobody can be told about.
    """
    everything = LicenceStore(db).all()
    return build_plan(everything, listings(db), channels(db), coverages(db, at, regime, rules), on)


def captures_for(db: Database, serial: int) -> Mapping[str, Capture]:
    """Return the captures behind one licence, by digest."""
    return {capture.digest: capture for capture in CaptureStore(db).for_licence(serial)}


def case_for(
    db: Database,
    licence: Licence,
    at: StayMonth,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
    thresholds: Thresholds | None = None,
) -> CaseFile:
    """Return the case file for one licence."""
    return build_case(
        licence=licence,
        reviews=ReviewStore(db).for_licence(licence.serial),
        channels=channels(db),
        coverage=coverage_for(db, licence, at, regime, rules),
        notices=RemediationStore(db).for_licence(licence.serial),
        pack=pack,
        at=at,
        captures=captures_for(db, licence.serial),
        thresholds=thresholds,
    )


def decisions(
    db: Database,
    at: StayMonth,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
    thresholds: Thresholds | None = None,
) -> tuple[Decision, ...]:
    """Return a decision for every active licence, heaviest first."""
    out = [
        case_for(db, licence, at, pack, regime, rules, thresholds).decision
        for licence in LicenceStore(db).with_status(LicenceStatus.ACTIVE)
    ]
    out.sort(key=lambda decision: (-decision.score, decision.licence_serial))
    return tuple(out)


def bundle_for(db: Database, serial: int, directory: Path) -> tuple[Path, int]:
    """Write the pages behind a licence out as a bundle, and say how many went.

    The bundle is the same shape the fetcher reads, so the whole pipeline can be
    run again against it years later with no network. A capture whose bytes were
    never kept is left out and the index says nothing about it, because a bundle
    that claims to hold a page it does not have is worse than a short one.
    """
    captures = CaptureStore(db)
    directory.mkdir(parents=True, exist_ok=True)
    entries: list[str] = []
    written = 0
    for capture in captures.for_licence(serial):
        if not captures.has_body(capture.digest):
            continue
        name = f"{capture.digest.removeprefix('sha256:')[:16]}.html"
        (directory / name).write_bytes(captures.body_of(capture.digest))
        entries.append("[[page]]")
        entries.append(f'url = "{capture.url}"')
        entries.append(f'body = "{name}"')
        entries.append(f"status = {capture.status}")
        if capture.etag:
            entries.append(f'etag = "{capture.etag}"')
        entries.append("")
        written += 1
    if not written:
        raise Invalid("bundle", serial, "no pages behind this licence have been kept")
    index = directory / INDEX
    index.write_text(NEWLINE.join(entries).rstrip() + NEWLINE, encoding="utf-8", newline=NEWLINE)
    return index, written


def monthly_return(
    db: Database,
    at: StayMonth,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Return:
    """Return the figures the unit files for a month."""
    return compile_return(
        at,
        LicenceStore(db).all(),
        coverages(db, at, regime, rules),
        decisions(db, at, pack, regime, rules),
    )


def calibration(
    db: Database,
    at: StayMonth,
    months: int = 12,
    tolerance: int = TOLERANCE,
) -> tuple[Drift, ...]:
    """Return what the last two spans say about each channel anchor table."""
    reviews = ReviewStore(db)
    found: list[Drift] = []
    for slug in ChannelStore(db).slugs():
        found.append(look_back(slug, reviews.for_channel(slug), at, months, tolerance))
    return tuple(found)


def quoted_digests(
    db: Database,
    at: StayMonth,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> set[str]:
    """Return the captures behind every quotation in a live case file."""
    held: set[str] = set()
    for licence in LicenceStore(db).with_status(LicenceStatus.ACTIVE):
        case = case_for(db, licence, at, pack, regime, rules)
        held.update(item.capture_digest for item in case.quotations)
    return held


def retention_plan(
    db: Database,
    before: dt.date,
    at: StayMonth,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Prune:
    """Return what a retention run would drop, protecting what is quoted."""
    return build_prune(db, before, quoted_digests(db, at, pack, regime, rules))


def localities(
    db: Database,
    at: StayMonth,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> tuple[Place, ...]:
    """Return the figures broken down by where the premises are."""
    return by_locality(
        LicenceStore(db).all(),
        coverages(db, at, regime, rules),
        decisions(db, at, pack, regime, rules),
    )
