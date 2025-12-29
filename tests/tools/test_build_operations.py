"""A runbook that quotes a threshold from two releases ago is worse than none."""

from __future__ import annotations

from tariffpeg.cli.context import EXIT_CODES
from tariffpeg.model.listing import CONFIRMATION_MONTHS
from tariffpeg.sample.regime import PUBLISHED as REGIME
from tariffpeg.tools import build_operations
from tariffpeg.tools.document import stale
from tariffpeg.triage.disposition import PUBLISHED as BANDS
from tariffpeg.triage.schedule import TARGET_DAYS
from tariffpeg.triage.weight import HALF_LIFE_MONTHS


def test_the_document_on_disk_is_what_the_code_would_write() -> None:
    assert stale(build_operations.DOCUMENT, build_operations.text()) == ""


def test_every_section_the_runbook_promises_is_there() -> None:
    text = build_operations.text()
    for heading in (
        "## Reading the channels",
        "## The sample",
        "## Weighing what was found",
        "## What happens next",
        "## Sending somebody out",
        "## What an exit code means",
    ):
        assert heading in text


def test_the_confirmation_span_is_read_off_the_code() -> None:
    assert f"every {CONFIRMATION_MONTHS} months" in build_operations.text()


def test_the_lookback_and_the_channel_count_are_read_off_the_regime() -> None:
    text = build_operations.text()
    assert f"last {REGIME.lookback_months} months" in text
    assert f"least {REGIME.minimum_channels} independent" in text


def test_every_base_quota_is_listed() -> None:
    text = build_operations.text()
    for season, quota in REGIME.base.items():
        assert f"| {season} | {quota} |" in text


def test_every_half_life_is_listed() -> None:
    text = build_operations.text()
    for kind, months in HALF_LIFE_MONTHS.items():
        assert f"| {kind} | {months} months |" in text


def test_the_bands_are_the_ones_in_force() -> None:
    text = build_operations.text()
    assert f"| re-inspection | {BANDS.reinspection:g} | {BANDS.access_reinspection:g} |" in text
    assert f"| urgent re-inspection | {BANDS.urgent:g} |" in text


def test_the_rule_that_a_short_sample_holds_the_disposition_is_written_down() -> None:
    assert "holds the disposition at a desk enquiry" in build_operations.text()


def test_every_visit_target_is_listed() -> None:
    text = build_operations.text()
    for kind, days in TARGET_DAYS.items():
        assert f"| {kind} | {days} working days |" in text


def test_every_exit_code_is_listed_with_what_it_means() -> None:
    text = build_operations.text()
    for name, code in EXIT_CODES.items():
        assert f"| {code} | {name} |" in text


def test_the_exit_codes_are_listed_in_order() -> None:
    lines = build_operations.text().splitlines()
    at = lines.index("## What an exit code means")
    codes = [int(line.split("|")[1]) for line in lines[at + 4 :] if line.startswith("| ")]
    assert codes == sorted(codes)


def test_the_generator_writes_and_checks_the_document() -> None:
    assert build_operations.main() == 0
