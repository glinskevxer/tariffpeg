"""Which page is which premises, on the command line."""

from __future__ import annotations

from tariffpeg.ids import format_licence_ref
from tests.cli.conftest import Run
from tests.cli.test_channel import ADD_CHANNEL, ADD_LICENCE, ADD_LISTING, REF


def test_a_listing_is_recorded_against_a_licence_and_a_channel(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    migrated(*ADD_LICENCE)
    result = migrated(*ADD_LISTING)
    assert result.exit_code == 0
    listed = migrated("listing", "list")
    assert "P-88213" in listed.output
    assert "/property/anchor-rooms/reviews" in listed.output


def test_a_listing_against_a_licence_nobody_registered_is_refused(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    assert migrated(*ADD_LISTING).exit_code == 3


def test_a_listing_on_a_channel_nobody_registered_is_refused(migrated: Run) -> None:
    migrated(*ADD_LICENCE)
    assert migrated(*ADD_LISTING).exit_code == 3


def test_two_licences_on_one_page_is_refused(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    migrated(*ADD_LICENCE)
    migrated(*ADD_LISTING)
    migrated(
        "licence",
        "add",
        "5000",
        "--name",
        "Quay",
        "--operator",
        "Y",
        "--locality",
        "Z",
        "--from",
        "2025-04-01",
        "--to",
        "2026-03-31",
        "--particular",
        "grading_band=2",
        "--particular",
        "let_rooms=4",
        "--particular",
        "bed_spaces=8",
    )
    result = migrated(
        "listing",
        "add",
        format_licence_ref(5000),
        "seaboard",
        "--path",
        "/property/other",
        "--property-ref",
        "P-88213",
    )
    assert result.exit_code == 4
    assert "property" in result.output


def test_a_listing_can_be_confirmed_afresh(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    migrated(*ADD_LICENCE)
    migrated(*ADD_LISTING)
    result = migrated("listing", "confirm", REF, "seaboard", "--on", "2026-06-01")
    assert result.exit_code == 0
    assert "2026-06-01" in migrated("listing", "list").output


def test_a_listing_can_be_retired_and_drops_out_of_the_listing(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    migrated(*ADD_LICENCE)
    migrated(*ADD_LISTING)
    result = migrated("listing", "retire", REF, "seaboard", "--why", "the page went")
    assert result.exit_code == 0
    assert "P-88213" not in migrated("listing", "list").output
    assert "P-88213" in migrated("listing", "list", "--all").output


def test_the_stale_listings_are_the_ones_nobody_has_looked_at(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    migrated(*ADD_LICENCE)
    migrated(*ADD_LISTING)
    assert "nothing needs checking" in migrated("listing", "stale", "--on", "2026-06-01").output
    assert "P-88213" in migrated("listing", "stale", "--on", "2028-01-01").output


def test_listings_can_be_read_a_licence_or_a_channel_at_a_time(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    migrated(*ADD_LICENCE)
    migrated(*ADD_LISTING)
    assert "P-88213" in migrated("listing", "list", "--licence", REF).output
    assert "P-88213" in migrated("listing", "list", "--channel", "seaboard").output
