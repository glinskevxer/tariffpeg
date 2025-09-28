"""Building a store and a recorded bundle for the harvest commands to read."""

from __future__ import annotations

from pathlib import Path

from tariffpeg.fetch.bundle import INDEX
from tariffpeg.ids import format_licence_ref
from tests.cli.conftest import Run
from tests.harvest.conftest import REVIEWS, page

REF = format_licence_ref(4021)
PROFILES = """
[[profile]]
channel = "seaboard"
version = 1
container = "article.review"
next_page = "a.next"

[[profile.field]]
name = "channel_review_id"
source = "attribute"
selector = "article.review"
attribute = "data-id"
required = true

[[profile.field]]
name = "title"
selector = "h3.title"

[[profile.field]]
name = "body"
selector = "p.body"
required = true

[[profile.field]]
name = "score"
source = "attribute"
selector = "span.score"
attribute = "data-value"
required = true

[[profile.field]]
name = "stay_month"
selector = "span.stay"
"""
BUNDLE_INDEX = """
[[page]]
url = "https://seaboard.example/robots.txt"
body = "robots.txt"
content_type = "text/plain"

[[page]]
url = "https://seaboard.example/property/4021/reviews"
body = "reviews.html"
"""


def stock(run: Run) -> None:
    """Put a channel, a licence and a listing on the register."""
    run("db", "migrate")
    run(
        "channel",
        "add",
        "seaboard",
        "--name",
        "Seaboard Stays",
        "--url",
        "https://seaboard.example",
        "--delay",
        "250",
        "--ceiling",
        "400",
    )
    run(
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
        "2025-01-01",
        "--to",
        "2026-12-31",
        "--particular",
        "grading_band=3",
        "--particular",
        "let_rooms=9",
        "--particular",
        "bed_spaces=18",
        "--particular",
        "lift=yes",
    )
    run(
        "listing",
        "add",
        REF,
        "seaboard",
        "--path",
        "/property/4021/reviews",
        "--property-ref",
        "P-88213",
        "--confirmed",
        "2025-08-01",
    )


def write_profiles(root: Path) -> Path:
    """Write the profile file and return its path."""
    target = root / "profiles.toml"
    target.write_text(PROFILES, encoding="utf-8")
    return target


def write_bundle(root: Path) -> Path:
    """Write a recorded bundle and return its directory."""
    directory = root / "bundle"
    directory.mkdir()
    (directory / INDEX).write_text(BUNDLE_INDEX, encoding="utf-8")
    (directory / "robots.txt").write_text("User-agent: *\n", encoding="utf-8")
    (directory / "reviews.html").write_text(page(REVIEWS), encoding="utf-8")
    return directory
