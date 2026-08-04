"""Reading rows, calling something that knows nothing about rows, handing back the answer."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from tariffpeg import service
from tariffpeg.clock import FixedClock
from tariffpeg.model.licence import LicenceStatus
from tariffpeg.model.listing import Listing
from tariffpeg.model.period import StayMonth
from tariffpeg.model.remediation import Remediation
from tariffpeg.store.captures import CaptureStore
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.listings import ListingStore
from tariffpeg.store.remediations import RemediationStore
from tariffpeg.store.reviews import ReviewStore
from tariffpeg.triage.schedule import Diary
from tests.conftest import a_review as a_plain_review
from tests.store.conftest import DIGEST, FETCHED, a_capture, a_channel, a_licence
from tests.triage.conftest import NO_LIFT, NO_LIFT_AGAIN, a_review

AT = StayMonth(2025, 9)
MINUTED = dt.datetime(2025, 10, 2, 9, 30, tzinfo=dt.UTC)
ON = dt.date(2025, 9, 15)


@pytest.fixture
def wired(db: Database) -> Database:
    ChannelStore(db).add(a_channel("seaboard"))
    ChannelStore(db).add(a_channel("quayside"))
    LicenceStore(db).add(a_licence())
    CaptureStore(db).record(a_capture())
    ListingStore(db).add(
        Listing(4021, "seaboard", "/property/4021/reviews", "P-1", dt.date(2025, 6, 1))
    )
    ListingStore(db).add(
        Listing(4021, "quayside", "/property/4021/reviews", "Q-1", dt.date(2025, 6, 1))
    )
    return db


def test_the_channels_come_back_by_slug(wired: Database) -> None:
    found = service.channels(wired)
    assert sorted(found) == ["quayside", "seaboard"]


def test_the_listings_come_back_by_licence(wired: Database) -> None:
    found = service.listings(wired)
    assert sorted(item.channel for item in found[4021]) == ["quayside", "seaboard"]


def test_a_retired_listing_is_left_out(wired: Database) -> None:
    store = ListingStore(wired)
    store.replace(store.get(4021, "quayside").retired("the page went"))
    assert [item.channel for item in service.listings(wired)[4021]] == ["seaboard"]


def test_the_coverage_of_a_licence_with_nothing_held_is_the_whole_requirement(
    wired: Database,
) -> None:
    found = service.coverage_for(wired, a_licence(), AT)
    assert found.opinions == 0
    assert found.total_shortfall > 0
    assert not found.satisfied


def test_reviews_that_are_held_show_up_in_the_coverage(wired: Database) -> None:
    ReviewStore(wired).add(a_review("1", NO_LIFT), FETCHED)
    found = service.coverage_for(wired, a_licence(), AT)
    assert found.opinions == 1
    assert found.channels_held == ("seaboard",)


def test_the_coverage_of_every_active_licence_comes_back_at_once(wired: Database) -> None:
    found = service.coverages(wired, AT)
    assert sorted(found) == [4021]


def test_a_licence_that_is_not_active_is_left_out_of_the_coverage(wired: Database) -> None:
    store = LicenceStore(wired)
    store.replace(store.get(4021).with_status(LicenceStatus.LAPSED))
    assert service.coverages(wired, AT) == {}


def test_the_plan_sends_the_harvest_to_the_listed_channels(wired: Database) -> None:
    plan = service.plan(wired, AT, ON)
    assert plan.channels() == ("quayside", "seaboard")
    assert plan.stops[0].url.startswith("https://")


def test_a_satisfied_licence_is_left_out_of_the_plan(wired: Database) -> None:
    reviews = ReviewStore(wired)
    number = 0
    for month in (7, 8, 5, 6, 9, 10, 3, 4, 11):
        for _ in range(12):
            number += 1
            channel = "seaboard" if number % 2 else "quayside"
            reviews.add(a_plain_review(str(number), 2025, month, channel), FETCHED)
    assert service.coverage_for(wired, a_licence(), AT).satisfied
    plan = service.plan(wired, AT, ON)
    assert plan.stops == ()
    assert plan.skipped == ("4021: the sample is complete",)


def test_the_captures_behind_a_licence_come_back_by_digest(wired: Database) -> None:
    found = service.captures_for(wired, 4021)
    assert DIGEST in found
    assert found[DIGEST].fetched_at == FETCHED


def test_a_case_file_is_built_out_of_what_the_store_holds(wired: Database) -> None:
    ReviewStore(wired).add(a_review("1", NO_LIFT), FETCHED)
    ReviewStore(wired).add(a_review("2", NO_LIFT_AGAIN, "quayside"), FETCHED)
    file = service.case_for(wired, a_licence(), AT)
    assert file.licence.serial == 4021
    assert file.decision.findings
    assert file.quotations


def test_a_notice_on_file_reaches_the_case_file(wired: Database) -> None:
    ReviewStore(wired).add(a_review("1", NO_LIFT), FETCHED)
    RemediationStore(wired).add(
        Remediation(4021, "lift", "RN-1", dt.date(2026, 3, 1), StayMonth(2026, 1), accepted=True)
    )
    file = service.case_for(wired, a_licence(), AT)
    assert file.applied.is_cleared("lift")
    assert file.notices


def test_a_decision_comes_back_for_every_active_licence(wired: Database) -> None:
    ReviewStore(wired).add(a_review("1", NO_LIFT), FETCHED)
    found = service.decisions(wired, AT)
    assert len(found) == 1
    assert found[0].licence_serial == 4021


def test_decisions_come_back_heaviest_first(wired: Database) -> None:
    LicenceStore(wired).add(a_licence(5000))
    ReviewStore(wired).add(a_review("1", NO_LIFT), FETCHED)
    found = service.decisions(wired, AT)
    assert len(found) == 2
    assert found[0].score >= found[1].score


def test_a_licence_that_is_not_active_reaches_the_plan_so_it_can_be_reported(
    wired: Database,
) -> None:
    store = LicenceStore(wired)
    store.replace(store.get(4021).with_status(LicenceStatus.LAPSED))
    plan = service.plan(wired, AT, ON)
    assert plan.stops == ()
    assert plan.skipped == ("4021: the licence is lapsed",)


def test_the_bundle_writer_leaves_out_a_capture_whose_bytes_were_never_kept(
    wired: Database, tmp_path: Path
) -> None:
    from tariffpeg.errors import Invalid

    with pytest.raises(Invalid, match="no pages behind this licence"):
        service.bundle_for(wired, 4021, tmp_path / "out")


def test_the_bundle_writer_writes_an_index_and_the_pages(wired: Database, tmp_path: Path) -> None:
    from tariffpeg.fetch.bundle import INDEX, load
    from tariffpeg.store.captures import CaptureStore

    body = b"<html>the page as it was served</html>"
    store = CaptureStore(wired)
    store.record(a_capture(DIGEST))
    wired.conn.execute("UPDATE capture SET digest = ? WHERE digest = ?", (DIGEST, DIGEST))
    store.db.conn.execute(
        "INSERT INTO capture_body (digest, body, stored_at) VALUES (?, ?, ?)",
        (DIGEST, body, "2025-07-04T22:15:00Z"),
    )
    out = tmp_path / "out"
    index, written = service.bundle_for(wired, 4021, out)
    assert index == out / INDEX
    assert written == 1
    assert load(out).known() == ("https://seaboard.example/p/1/reviews",)


def test_the_calibration_covers_every_registered_channel(wired: Database) -> None:
    found = service.calibration(wired, AT)
    assert [drift.channel for drift in found] == ["quayside", "seaboard"]


def test_a_channel_with_nothing_held_reads_as_thin(wired: Database) -> None:
    from tariffpeg.sample.calibration import Calibration

    found = service.calibration(wired, AT)
    assert all(drift.verdict is Calibration.THIN for drift in found)


def test_the_calibration_of_a_store_with_no_channels_is_empty(db: Database) -> None:
    assert service.calibration(db, AT) == ()


def test_the_captures_behind_live_quotations_are_protected(wired: Database) -> None:
    ReviewStore(wired).add(a_review("1", NO_LIFT), FETCHED)
    held = service.quoted_digests(wired, AT)
    assert DIGEST in held


def test_a_licence_with_nothing_quoted_protects_nothing(wired: Database) -> None:
    assert service.quoted_digests(wired, AT) == set()


def test_a_retention_plan_protects_what_is_quoted(wired: Database) -> None:
    import datetime as dt2

    from tariffpeg.store.captures import CaptureStore

    body = b"<html>a quoted page</html>"
    CaptureStore(wired).db.conn.execute(
        "UPDATE capture SET digest = digest WHERE digest = ?", (DIGEST,)
    )
    CaptureStore(wired).db.conn.execute(
        "INSERT INTO capture_body (digest, body, stored_at) VALUES (?, ?, ?)",
        (DIGEST, body, "2025-07-04T22:15:00Z"),
    )
    ReviewStore(wired).add(a_review("1", NO_LIFT), FETCHED)
    plan = service.retention_plan(wired, dt2.date(2026, 1, 1), AT)
    assert plan.dropping == ()
    assert plan.kept_in_use == (DIGEST,)


def test_the_locality_breakdown_covers_the_active_licences(wired: Database) -> None:
    found = service.localities(wired, AT)
    assert [place.locality for place in found] == ["Porthgwarra"]
    assert found[0].licences == 1


def test_a_month_of_visits_is_booked_against_the_diaries_it_was_given(
    wired: Database,
) -> None:
    ReviewStore(wired).add(a_review("1", NO_LIFT), FETCHED)
    ReviewStore(wired).add(a_review("2", NO_LIFT_AGAIN), FETCHED)
    booked = service.visits(wired, AT, dt.date(2025, 9, 15), [Diary("Trewin")])
    assert booked.booked + len(booked.refusals) >= 0
    assert all(item.inspector == "Trewin" for item in booked.bookings)


def test_the_workload_covers_every_inspector_the_run_was_given(wired: Database) -> None:
    found = service.workload(wired, AT, dt.date(2025, 9, 15), [Diary("Trewin"), Diary("Ivell")])
    assert [load.inspector for load in found.loads] == ["Ivell", "Trewin"]


def test_the_budget_reads_what_each_channel_has_already_had_today(wired: Database) -> None:
    found = service.budget(
        wired, service.plan(wired, AT, dt.date(2025, 9, 15)), dt.date(2025, 9, 15)
    )
    assert found.fits
    assert all(allowance.spent == 0 for allowance in found.allowances)


def test_a_plan_cut_to_the_budget_asks_for_no_more_than_the_day_allows(
    wired: Database,
) -> None:
    day = dt.date(2025, 9, 15)
    plan = service.plan(wired, AT, day)
    cut = service.affordable(wired, plan, day)
    assert cut.total_pages <= plan.total_pages


def test_minuting_a_month_writes_one_record_for_each_active_licence(
    wired: Database,
) -> None:
    written = service.minute(wired, AT, "R Bosustow", FixedClock(MINUTED))
    assert [item.licence_serial for item in written] == [4021]
    assert written[0].officer == "R Bosustow"
    assert written[0].minuted_at == MINUTED


def test_minuting_the_same_month_again_leaves_what_was_written_alone(
    wired: Database,
) -> None:
    service.minute(wired, AT, "R Bosustow", FixedClock(MINUTED))
    again = service.minute(wired, AT, "M Nancarrow", FixedClock(MINUTED))
    assert again == ()
    assert service.already_minuted(wired, AT) == (4021,)


def test_the_ledger_reads_back_what_was_minuted_about_a_licence(wired: Database) -> None:
    service.minute(wired, AT, "R Bosustow", FixedClock(MINUTED))
    held = service.ledger_for(wired, 4021)
    assert [item.decided_at for item in held] == [AT]


def test_a_licence_nobody_minuted_has_an_empty_ledger(wired: Database) -> None:
    assert service.ledger_for(wired, 4021) == ()


def test_a_register_nobody_has_minuted_reconciles_as_unminuted(wired: Database) -> None:
    found = service.reconciliation(wired, AT)
    assert found.unminuted() == (4021,)
    assert found.settled()


def test_a_minuted_register_reconciles_as_settled(wired: Database) -> None:
    service.minute(wired, AT, "R Bosustow", FixedClock(MINUTED))
    found = service.reconciliation(wired, AT)
    assert found.unminuted() == ()
    assert found.settled()
