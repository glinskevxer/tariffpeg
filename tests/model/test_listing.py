"""Two guesthouses on one street share a name often enough that guessing is out."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.model.listing import Listing

AGENT = "tariffpeg-harvester (standards@example-authority.test)"


def channel(slug: str = "seaboard") -> Channel:
    return Channel(
        slug=slug,
        name=slug.title(),
        base_url=f"https://{slug}.example",
        syndication=SyndicationClass.PRIMARY,
        policy=FetchPolicy(AGENT, 1500, 400),
    )


def listing(**over: object) -> Listing:
    base: dict[str, object] = {
        "licence_serial": 4021,
        "channel": "seaboard",
        "path": "/property/anchor-rooms/reviews",
        "property_ref": "P-88213",
        "confirmed_on": dt.date(2025, 4, 1),
    }
    base.update(over)
    return Listing(**base)  # type: ignore[arg-type]


def test_the_key_pairs_the_licence_with_the_channel() -> None:
    assert listing().key == "4021:seaboard"


def test_the_url_hangs_the_path_off_the_channel_base() -> None:
    assert listing().url(channel()) == "https://seaboard.example/property/anchor-rooms/reviews"


def test_asking_a_different_channel_for_the_url_is_refused() -> None:
    with pytest.raises(Invalid, match="different channel"):
        listing().url(channel("quayside"))


def test_a_path_that_does_not_start_at_the_root_is_refused() -> None:
    with pytest.raises(Invalid, match="starts at the root"):
        listing(path="property/anchor-rooms")


def test_a_path_with_a_trailing_slash_is_refused_unless_it_is_the_root() -> None:
    with pytest.raises(Invalid, match="no trailing slash"):
        listing(path="/property/anchor-rooms/")
    assert listing(path="/").path == "/"


def test_a_listing_belongs_to_a_channel_slug_and_a_real_serial() -> None:
    with pytest.raises(Invalid, match="channel slug"):
        listing(channel="Seaboard Stays")
    with pytest.raises(Invalid, match="not negative"):
        listing(licence_serial=-1)


def test_the_channel_has_to_number_the_property() -> None:
    with pytest.raises(Invalid, match="numbers this property"):
        listing(property_ref="   ")


def test_a_confirmation_goes_stale_after_the_published_span() -> None:
    held = listing(confirmed_on=dt.date(2025, 4, 1))
    assert not held.stale_on(dt.date(2026, 9, 30))
    assert held.stale_on(dt.date(2026, 10, 1))
    assert held.stale_on(dt.date(2027, 1, 1))


def test_a_confirmation_on_the_same_day_of_the_month_counts_that_month() -> None:
    held = listing(confirmed_on=dt.date(2025, 4, 15))
    assert not held.stale_on(dt.date(2026, 10, 14))
    assert held.stale_on(dt.date(2026, 10, 15))


def test_confirming_a_listing_moves_its_date_and_leaves_the_rest() -> None:
    fresh = listing().confirmed(dt.date(2026, 5, 1))
    assert fresh.confirmed_on == dt.date(2026, 5, 1)
    assert fresh.path == listing().path
    assert fresh.active


def test_retiring_a_listing_marks_it_and_records_why() -> None:
    gone = listing().retired("the channel took the page down")
    assert not gone.active
    assert "took the page down" in gone.note


def test_retiring_without_a_reason_is_refused() -> None:
    with pytest.raises(Invalid, match="says why it was retired"):
        listing().retired("   ")


def test_a_listing_is_active_unless_it_is_retired() -> None:
    assert listing().active
    assert listing().note == ""
