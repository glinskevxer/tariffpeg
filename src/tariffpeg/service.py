"""The layer that puts the store together with the rules.

Everything below this is either a pure function or a table. This is where the
two meet, and it is deliberately thin: reading rows, calling something that
knows nothing about rows, and handing back the answer. Anything here that starts
making decisions belongs one layer down where it can be tested without a store.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

from tariffpeg.claims.pack import PACK
from tariffpeg.claims.rules import RulePack
from tariffpeg.dedupe.syndication import DEFAULT_RULES, SyndicationRules
from tariffpeg.harvest.plan import Plan
from tariffpeg.harvest.plan import build as build_plan
from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.listing import Listing
from tariffpeg.model.period import StayMonth
from tariffpeg.report.casefile import CaseFile
from tariffpeg.report.casefile import build as build_case
from tariffpeg.sample.coverage import Coverage, measure
from tariffpeg.sample.regime import PUBLISHED, Regime
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.listings import ListingStore
from tariffpeg.store.remediations import RemediationStore
from tariffpeg.store.reviews import ReviewStore
from tariffpeg.triage.disposition import Decision, Thresholds


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
    """Return the plan for the next harvest."""
    active = LicenceStore(db).with_status(LicenceStatus.ACTIVE)
    return build_plan(active, listings(db), channels(db), coverages(db, at, regime, rules), on)


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
