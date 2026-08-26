"""The layer that puts the store together with the rules.

Everything below this is either a pure function or a table. This is where the
two meet, and it is deliberately thin: reading rows, calling something that
knows nothing about rows, and handing back the answer. Anything here that starts
making decisions belongs one layer down where it can be tested without a store.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from pathlib import Path

from tariffpeg.claims.pack import PACK
from tariffpeg.claims.rules import RulePack
from tariffpeg.clock import Clock
from tariffpeg.dedupe.syndication import DEFAULT_RULES, SyndicationRules
from tariffpeg.errors import Conflict, Invalid
from tariffpeg.fetch.bundle import INDEX
from tariffpeg.harvest.budget import Budget, spend_by_channel, trim
from tariffpeg.harvest.budget import measure as measure_budget
from tariffpeg.harvest.plan import Plan
from tariffpeg.harvest.plan import build as build_plan
from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel
from tariffpeg.model.determination import Determination
from tariffpeg.model.licence import Licence, LicenceStatus
from tariffpeg.model.listing import Listing
from tariffpeg.model.period import StayMonth
from tariffpeg.report.casefile import CaseFile
from tariffpeg.report.casefile import build as build_case
from tariffpeg.report.health import FAULT, Health, Reading, clear, fault, warning
from tariffpeg.report.locality import Place, by_locality
from tariffpeg.report.movement import Reconciliation, reconcile
from tariffpeg.report.notice import Draft, reminder
from tariffpeg.report.notice import draft as draft_letter
from tariffpeg.report.summary import Return, compile_return
from tariffpeg.report.workload import Spread, spread
from tariffpeg.sample.calibration import TOLERANCE, Drift, look_back
from tariffpeg.sample.coverage import Coverage, measure
from tariffpeg.sample.regime import PUBLISHED, Regime
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.determinations import DeterminationStore
from tariffpeg.store.letters import LetterStore
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.listings import ListingStore
from tariffpeg.store.migrations import current_version, drift
from tariffpeg.store.remediations import RemediationStore
from tariffpeg.store.retention import Prune
from tariffpeg.store.retention import plan as build_prune
from tariffpeg.store.reviews import ReviewStore
from tariffpeg.triage.disposition import Decision, Thresholds
from tariffpeg.triage.schedule import Diary, Round, Scheduler, book_all

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


def visits(
    db: Database,
    at: StayMonth,
    decided_on: dt.date,
    diaries: Sequence[Diary],
    holidays: frozenset[dt.date] = frozenset(),
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Round:
    """Book a visit for everything a month's decisions ask for."""
    licences = {licence.serial: licence for licence in LicenceStore(db).all()}
    wanted = [
        (licences[decision.licence_serial], decision.disposition)
        for decision in decisions(db, at, pack, regime, rules)
    ]
    return book_all(Scheduler(diaries, holidays), wanted, decided_on)


def workload(
    db: Database,
    at: StayMonth,
    decided_on: dt.date,
    diaries: Sequence[Diary],
    holidays: frozenset[dt.date] = frozenset(),
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Spread:
    """Return what a month's visits would do to each inspector's diary."""
    round_ = visits(db, at, decided_on, diaries, holidays, pack, regime, rules)
    return spread(round_.bookings, diaries, round_.late)


def budget(db: Database, plan: Plan, on: dt.date) -> Budget:
    """Return what a plan would cost each channel against what the day has left."""
    known = channels(db)
    captures = CaptureStore(db)
    spent = spend_by_channel(list(known), {slug: captures.spent_on(slug, on) for slug in known})
    return measure_budget(plan, known, spent)


def affordable(db: Database, plan: Plan, on: dt.date) -> Plan:
    """Return the plan cut down to what the channels will allow today."""
    return trim(plan, budget(db, plan, on))


def minute(
    db: Database,
    at: StayMonth,
    officer: str,
    clock: Clock,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> tuple[Determination, ...]:
    """Write a month's decisions into the ledger and return what was written.

    A licence already minuted for the month is left as it was. Re-running the
    minute after a late harvest is meant to pick up the licences that were not
    on the register the first time, not to rewrite what the operator was told.
    """
    ledger = DeterminationStore(db)
    taken = clock.now()
    written: list[Determination] = []
    for decision in decisions(db, at, pack, regime, rules):
        if ledger.exists(decision.licence_serial, at):
            continue
        record = Determination(
            licence_serial=decision.licence_serial,
            decided_at=at,
            disposition=decision.disposition,
            score=decision.score,
            access_score=decision.access_score,
            capped=decision.capped,
            pack_version=pack.version,
            minuted_at=taken,
            officer=officer,
        )
        ledger.record(record)
        written.append(record)
    return tuple(written)


def already_minuted(db: Database, at: StayMonth) -> tuple[int, ...]:
    """Return the licences the ledger already holds a minute for in a month."""
    return tuple(item.licence_serial for item in DeterminationStore(db).at_month(at))


def ledger_for(db: Database, serial: int) -> tuple[Determination, ...]:
    """Return every minute the ledger holds about one licence."""
    return DeterminationStore(db).for_licence(serial)


def reconciliation(
    db: Database,
    at: StayMonth,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Reconciliation:
    """Return the ledger set against the reading the evidence gives now."""
    ledger = DeterminationStore(db)
    live = decisions(db, at, pack, regime, rules)
    minutes = {
        decision.licence_serial: ledger.latest_for(decision.licence_serial) for decision in live
    }
    return reconcile(minutes, live, pack.version)


def letter_draft(
    db: Database,
    licence: Licence,
    at: StayMonth,
    sent_on: dt.date,
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Draft:
    """Return the letter one licence's case file would produce."""
    return draft_letter(
        case_for(db, licence, at, pack, regime, rules),
        DeterminationStore(db).latest_for(licence.serial),
        sent_on,
    )


def chase(
    db: Database,
    on: dt.date,
    holidays: frozenset[dt.date] = frozenset(),
) -> tuple[tuple[Draft, ...], tuple[str, ...]]:
    """Return a reminder for every letter that is late, and what was left alone.

    A licence that has had its reminders is not chased again. It comes back in
    the second tuple with the reason, because a run that quietly drops those is
    a run whose output cannot be filed.
    """
    letters = LetterStore(db)
    drafts: list[Draft] = []
    left: list[str] = []
    for letter in letters.overdue_on(on, holidays):
        already = letters.chased(letter.licence_serial)
        try:
            drafts.append(reminder(letter, already, on))
        except Conflict as err:
            left.append(f"{letter.reference}: {err.reason}")
    return tuple(drafts), tuple(left)


def health(
    db: Database,
    at: StayMonth,
    on: dt.date,
    holidays: frozenset[dt.date] = frozenset(),
    pack: RulePack = PACK,
    regime: Regime = PUBLISHED,
    rules: SyndicationRules = DEFAULT_RULES,
) -> Health:
    """Return one reading of whether the unit is keeping up.

    The store is checked first and the rest is only worth reading if it passed.
    A file that does not verify will happily answer every other question here,
    wrongly, and a warning about an unminuted month is not what anybody needs to
    see about a corrupt store.
    """
    readings = [_store_reading(db)]
    if readings[0].state != FAULT:
        readings.extend(
            (
                _letters_reading(db, on, holidays),
                _ledger_reading(db, at, pack, regime, rules),
                _sample_reading(db, at, regime, rules),
            )
        )
    return Health(tuple(readings))


def _store_reading(db: Database) -> Reading:
    problems = [*db.integrity_problems(), *drift(db), *CaptureStore(db).body_problems()]
    if problems:
        return fault("store", problems[0])
    return clear("store", f"schema version {current_version(db)}")


def _letters_reading(db: Database, on: dt.date, holidays: frozenset[dt.date]) -> Reading:
    late = LetterStore(db).overdue_on(on, holidays)
    if not late:
        return clear("letters", "nothing is waiting on an answer")
    return warning("letters", f"{len(late)} letters are past their reply day")


def _ledger_reading(
    db: Database,
    at: StayMonth,
    pack: RulePack,
    regime: Regime,
    rules: SyndicationRules,
) -> Reading:
    found = reconciliation(db, at, pack, regime, rules)
    wanting = found.wanting_a_letter()
    if wanting:
        return warning("ledger", f"{len(wanting)} licences read worse than the operator was told")
    never = found.unminuted()
    if never:
        return warning("ledger", f"{len(never)} licences have never been minuted")
    return clear("ledger", "every licence reads the way it was minuted")


def _sample_reading(
    db: Database, at: StayMonth, regime: Regime, rules: SyndicationRules
) -> Reading:
    short = [found for found in coverages(db, at, regime, rules).values() if not found.satisfied]
    if not short:
        return clear("sample", "every licence is properly sampled")
    return warning("sample", f"{len(short)} licences are short of their sample")
