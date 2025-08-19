"""A quotation that cannot be answered for should not be in the file."""

from __future__ import annotations

import datetime as dt

from tariffpeg.claims.pack import PACK
from tariffpeg.model.capture import Capture
from tariffpeg.model.channel import Channel
from tariffpeg.model.licence import Licence
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.model.remediation import Remediation
from tariffpeg.model.review import Review
from tariffpeg.report.casefile import build
from tariffpeg.sample.coverage import Coverage, SeasonCoverage
from tariffpeg.triage.disposition import Disposition
from tariffpeg.triage.schedule import Booking, Refusal
from tests.triage.conftest import DIGEST, NO_LIFT, NO_LIFT_AGAIN, a_review

AT = StayMonth(2025, 9)
WINDOW = (StayMonth(2024, 7), StayMonth(2026, 6))
FETCHED = dt.datetime(2025, 8, 1, 9, 30, tzinfo=dt.UTC)
QUIET = "Breakfast was lovely and the beds were comfortable for the whole week."


def coverage(satisfied: bool = True) -> Coverage:
    held = 12 if satisfied else 1
    return Coverage(
        serial=4021,
        seasons=(
            SeasonCoverage(Season.PEAK, 12, held),
            SeasonCoverage(Season.SHOULDER, 0, 0),
            SeasonCoverage(Season.OFF, 0, 0),
        ),
        channels_held=("quayside", "seaboard"),
        channels_wanted=2,
        window=WINDOW,
        opinions=held,
    )


def captures() -> dict[str, Capture]:
    return {
        DIGEST: Capture(
            digest=DIGEST,
            channel="seaboard",
            url="https://seaboard.example/p/1",
            final_url="https://seaboard.example/p/1",
            status=200,
            fetched_at=FETCHED,
            byte_count=2048,
            profile_key="seaboard/v1",
            licence_serial=4021,
        )
    }


def reviews() -> tuple[Review, ...]:
    return (a_review("1", NO_LIFT), a_review("2", NO_LIFT_AGAIN, "quayside"))


def notice(accepted: bool = True) -> Remediation:
    return Remediation(
        licence_serial=4021,
        claim_key="lift",
        reference="RN-2026-0118",
        filed_on=dt.date(2026, 3, 4),
        effective_from=StayMonth(2026, 1),
        accepted=accepted,
    )


def test_the_file_names_the_licence_and_the_disposition(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures())
    heading = file.heading()
    assert heading[0].startswith(anchor.ref)
    assert "The Anchor Rooms" in heading[0]
    assert "3 keys" in heading[1]
    assert str(file.decision.disposition) in heading[2]


def test_reviews_of_another_licence_are_left_out(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    elsewhere = Review(
        channel="seaboard",
        channel_review_id="99",
        licence_serial=9999,
        stay=StayMonth(2025, 7),
        unit_points=74,
        raw_score="8.4",
        body=NO_LIFT,
        capture_digest=DIGEST,
        profile_key="seaboard/v1",
    )
    file = build(anchor, (*reviews(), elsewhere), channels, coverage(), [], PACK, AT, captures())
    assert all(item.review_key != "seaboard:99" for item in file.quotations)


def test_every_quotation_carries_its_digest_and_the_time_it_was_served(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures())
    assert file.quotations
    for item in file.quotations:
        assert item.capture_digest.startswith("sha256:")
        assert item.fetched_at == FETCHED
        assert "served 2025-08-01" in item.line()


def test_a_quotation_with_no_capture_on_file_says_so(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, reviews(), channels, coverage(), [], PACK, AT)
    assert all("not on file" in item.line() for item in file.quotations)


def test_the_findings_block_carries_the_quotations_under_each_finding(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures())
    block = file.findings_block()
    assert block[0].startswith("lift (")
    assert any(line.startswith("  2025-07 on") for line in block)
    assert len(file.quotations_for("lift")) >= 2


def test_a_licence_with_nothing_against_it_says_so(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, (a_review("1", QUIET),), channels, coverage(), [], PACK, AT, captures())
    assert file.findings_block() == ("nothing was found against the particulars on this licence",)
    assert file.decision.disposition is Disposition.NO_ACTION


def test_a_file_with_no_notices_says_so(anchor: Licence, channels: dict[str, Channel]) -> None:
    file = build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures())
    assert file.remediation_block() == ("no remediation notices are on file",)


def test_an_accepted_notice_shows_the_discount_it_caused(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, reviews(), channels, coverage(), [notice()], PACK, AT, captures())
    block = file.remediation_block()
    assert any("RN-2026-0118 on lift" in line for line in block)
    assert any("cut from" in line for line in block)
    assert file.applied.is_cleared("lift")


def test_a_cleared_particular_is_marked_in_the_findings(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, reviews(), channels, coverage(), [notice()], PACK, AT, captures())
    assert any("predates an accepted remediation" in line for line in file.findings_block())


def test_an_unaccepted_notice_is_listed_but_discounts_nothing(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, reviews(), channels, coverage(), [notice(False)], PACK, AT, captures())
    assert any("not accepted" in line for line in file.remediation_block())
    assert file.applied.discounts == ()


def test_a_short_sample_holds_the_disposition_and_the_file_says_what_would_help(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, reviews(), channels, coverage(satisfied=False), [], PACK, AT, captures())
    assert file.decision.capped
    assert any("completing the sample" in line for line in file.what_would_change_this())


def test_a_file_with_no_visit_sought_says_so(anchor: Licence, channels: dict[str, Channel]) -> None:
    file = build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures())
    assert file.visit_block() == ("no visit was sought",)


def test_a_booked_visit_names_the_inspector_and_the_day(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    booking = Booking(4021, "Trewin", dt.date(2025, 9, 10), Disposition.REINSPECTION)
    file = build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures(), visit=booking)
    assert file.visit_block() == ("Trewin to visit on 2025-09-10",)


def test_a_visit_that_could_not_be_booked_says_why(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    refusal = Refusal(4021, "nobody was free inside the licence period")
    file = build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures(), visit=refusal)
    assert "nobody was free" in file.visit_block()[0]


def test_the_whole_file_reads_as_headed_blocks(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    lines = build(anchor, reviews(), channels, coverage(), [], PACK, AT, captures()).lines()
    for heading in ("IDENTITY", "WHY", "SAMPLE", "FINDINGS", "REMEDIATION", "VISIT"):
        assert heading in lines
    assert lines[-1] != ""


def test_the_file_says_what_would_raise_a_licence_with_nothing_against_it(
    anchor: Licence, channels: dict[str, Channel]
) -> None:
    file = build(anchor, (a_review("1", QUIET),), channels, coverage(), [], PACK, AT, captures())
    assert any("one more corroborating voice" in line for line in file.what_would_change_this())
