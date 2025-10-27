"""The agreed terms are typed in once and read off a column afterwards."""

from __future__ import annotations

import pytest

from tariffpeg.cli.channel import parse_window
from tariffpeg.errors import Invalid
from tariffpeg.ids import format_licence_ref
from tariffpeg.model.channel import ALWAYS, CourtesyWindow
from tests.cli.conftest import Run
from tests.conftest import AGENT

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


def test_a_channel_row_carries_the_agreed_terms() -> None:
    from tariffpeg.cli.channel import as_row
    from tariffpeg.model.channel import Channel, CourtesyWindow, FetchPolicy, SyndicationClass

    channel = Channel(
        slug="seaboard",
        name="Seaboard Stays",
        base_url="https://seaboard.example",
        syndication=SyndicationClass.PRIMARY,
        policy=FetchPolicy(AGENT, 1500, 400, window=CourtesyWindow(22, 6)),
    )
    row = as_row(channel)
    assert row["delay"] == 1500
    assert row["window"] == "22-6"
