"""The agreed terms are typed in once and read off a column afterwards."""

from __future__ import annotations

import pytest

from tariffpeg.cli.channel import parse_window
from tariffpeg.errors import Invalid
from tariffpeg.ids import format_licence_ref
from tariffpeg.model.channel import ALWAYS, CourtesyWindow
from tests.cli.conftest import Run

REF = format_licence_ref(4021)
ADD_CHANNEL = (
    "channel",
    "add",
    "seaboard",
    "--name",
    "Seaboard Stays",
    "--url",
    "https://seaboard.example",
    "--delay",
    "1500",
    "--ceiling",
    "400",
    "--window",
    "22-6",
    "--pages",
    "8",
)
ADD_LICENCE = (
    "licence",
    "add",
    "4021",
    "--name",
    "The Anchor Rooms",
    "--operator",
    "Pellow and Daughter",
    "--locality",
    "Porthgwarra",
    "--from",
    "2025-04-01",
    "--to",
    "2026-03-31",
    "--particular",
    "grading_band=3",
    "--particular",
    "let_rooms=9",
    "--particular",
    "bed_spaces=18",
)
ADD_LISTING = (
    "listing",
    "add",
    REF,
    "seaboard",
    "--path",
    "/property/anchor-rooms/reviews",
    "--property-ref",
    "P-88213",
    "--confirmed",
    "2026-01-05",
)


def test_a_window_is_read_from_two_hours_with_a_dash() -> None:
    assert parse_window("22-6") == CourtesyWindow(22, 6)
    assert parse_window("") is ALWAYS


def test_a_window_written_any_other_way_is_refused() -> None:
    with pytest.raises(Invalid, match="write it as 22-6"):
        parse_window("22 to 6")
    with pytest.raises(Invalid, match="whole hours"):
        parse_window("ten-six")


def test_a_channel_is_registered_and_reads_back(migrated: Run) -> None:
    result = migrated(*ADD_CHANNEL)
    assert result.exit_code == 0
    listed = migrated("channel", "list")
    assert "seaboard" in listed.output
    assert "1500" in listed.output
    assert "22-6" in listed.output


def test_the_agent_string_comes_from_the_settings(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    shown = migrated("channel", "show", "seaboard")
    assert "tariffpeg-harvester" in shown.output
    assert "robots at https://seaboard.example/robots.txt" in shown.output


def test_the_dial_anchors_are_printed(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    shown = migrated("channel", "show", "seaboard")
    assert "8 is very good" in shown.output


def test_a_channel_on_something_other_than_https_is_refused(migrated: Run) -> None:
    result = migrated(
        "channel", "add", "seaboard", "--name", "X", "--url", "http://seaboard.example"
    )
    assert result.exit_code == 2
    assert "https only" in result.output


def test_a_crawl_delay_under_the_floor_is_refused(migrated: Run) -> None:
    result = migrated(*ADD_CHANNEL, "--delay", "10")
    assert result.exit_code == 2
    assert "floor for any channel" in result.output


def test_the_same_channel_twice_is_refused(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    assert migrated(*ADD_CHANNEL).exit_code == 4


def test_channels_can_be_read_a_kind_at_a_time(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    migrated(
        "channel",
        "add",
        "atlas",
        "--name",
        "Atlas",
        "--url",
        "https://atlas.example",
        "--syndication",
        "aggregator",
    )
    assert "atlas" in migrated("channel", "list", "--syndication", "aggregator").output
    assert "seaboard" not in migrated("channel", "list", "--syndication", "aggregator").output


def test_a_channel_can_be_taken_off_the_register(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    assert migrated("channel", "remove", "seaboard", "--yes").exit_code == 0
    assert "seaboard" not in migrated("channel", "list").output


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
