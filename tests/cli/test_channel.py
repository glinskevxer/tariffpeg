"""The agreed terms are typed in once and read off a column afterwards."""

from __future__ import annotations

from pathlib import Path

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


def probe_bundle(root: Path, robots: str, status: int = 200) -> Path:
    """Write a bundle carrying one robots file and return its directory."""
    from tariffpeg.fetch.bundle import INDEX

    directory = root / "probe"
    directory.mkdir()
    (directory / "robots.txt").write_text(robots, encoding="utf-8")
    (directory / INDEX).write_text(
        '[[page]]\nurl = "https://seaboard.example/robots.txt"\n'
        f'body = "robots.txt"\nstatus = {status}\n',
        encoding="utf-8",
    )
    return directory


def test_a_probe_sets_the_published_delay_against_the_agreed_one(
    migrated: Run, tmp_path: Path
) -> None:
    migrated(*ADD_CHANNEL)
    bundle = probe_bundle(tmp_path, "User-agent: *\nCrawl-delay: 30\n")
    result = migrated("channel", "probe", "seaboard", "--bundle", str(bundle))
    assert result.exit_code == 0
    assert "crawl delay in ms" in result.output
    assert "30000" in result.output


def test_a_probe_says_the_agreed_delay_stands_when_none_is_published(
    migrated: Run, tmp_path: Path
) -> None:
    migrated(*ADD_CHANNEL)
    bundle = probe_bundle(tmp_path, "User-agent: *\n")
    result = migrated("channel", "probe", "seaboard", "--bundle", str(bundle))
    assert "none" in result.output
    assert "1500" in result.output


def test_a_probe_lists_the_sitemaps_a_channel_publishes(migrated: Run, tmp_path: Path) -> None:
    robots = "User-agent: *\nSitemap: https://seaboard.example/sitemap.xml\n"
    migrated(*ADD_CHANNEL)
    bundle = probe_bundle(tmp_path, robots)
    result = migrated("channel", "probe", "seaboard", "--bundle", str(bundle))
    assert "sitemaps: https://seaboard.example/sitemap.xml" in result.output


def test_a_probe_says_which_of_our_pages_the_robots_file_disallows(
    migrated: Run, tmp_path: Path
) -> None:
    migrated(*ADD_CHANNEL)
    migrated(*ADD_LICENCE)
    migrated(*ADD_LISTING)
    bundle = probe_bundle(tmp_path, "User-agent: *\nDisallow: /property\n")
    result = migrated("channel", "probe", "seaboard", "--bundle", str(bundle))
    assert "DISALLOWED" in result.output
    assert "/property/anchor-rooms/reviews" in result.output


def test_a_probe_says_when_our_pages_are_allowed(migrated: Run, tmp_path: Path) -> None:
    migrated(*ADD_CHANNEL)
    migrated(*ADD_LICENCE)
    migrated(*ADD_LISTING)
    bundle = probe_bundle(tmp_path, "User-agent: *\nDisallow: /admin\n")
    result = migrated("channel", "probe", "seaboard", "--bundle", str(bundle))
    assert "allowed" in result.output
    assert "DISALLOWED" not in result.output


def test_a_probe_of_a_channel_with_no_listings_says_so(migrated: Run, tmp_path: Path) -> None:
    migrated(*ADD_CHANNEL)
    bundle = probe_bundle(tmp_path, "User-agent: *\n")
    result = migrated("channel", "probe", "seaboard", "--bundle", str(bundle))
    assert "no listings are recorded on this channel" in result.output


def test_a_probe_says_when_the_channel_could_not_serve_its_robots_file(
    migrated: Run, tmp_path: Path
) -> None:
    migrated(*ADD_CHANNEL)
    bundle = probe_bundle(tmp_path, "", status=500)
    result = migrated("channel", "probe", "seaboard", "--bundle", str(bundle))
    assert "could not serve its robots file" in result.output


def test_a_probe_with_no_transport_named_is_refused(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    result = migrated("channel", "probe", "seaboard")
    assert result.exit_code == 2
    assert "--bundle to replay or --live" in result.output


def test_a_probe_of_a_channel_nobody_registered_is_refused(migrated: Run, tmp_path: Path) -> None:
    bundle = probe_bundle(tmp_path, "User-agent: *\n")
    assert migrated("channel", "probe", "nowhere", "--bundle", str(bundle)).exit_code == 3


def test_the_calibration_of_a_channel_with_nothing_held_reads_as_thin(
    migrated: Run,
) -> None:
    migrated(*ADD_CHANNEL)
    result = migrated("channel", "calibration", "--at", "2026-06")
    assert result.exit_code == 0
    assert "seaboard" in result.output
    assert "too few reviews to say" in result.output


def test_the_calibration_of_a_store_with_no_channels_says_so(migrated: Run) -> None:
    assert "no channels are registered" in migrated("channel", "calibration").output


def test_the_calibration_can_be_asked_for_as_comma_separated_text(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    result = migrated("channel", "calibration", "--at", "2026-06", extra=["--csv"])
    assert result.output.splitlines()[0].startswith("channel,earlier median,later median")


def test_a_span_of_no_months_is_refused(migrated: Run) -> None:
    migrated(*ADD_CHANNEL)
    result = migrated("channel", "calibration", "--at", "2026-06", "--months", "0")
    assert result.exit_code == 2
    assert "a month or more" in result.output
