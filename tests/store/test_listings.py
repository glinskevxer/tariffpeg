"""Two licences pointed at one page is the mistake this catches."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.listing import Listing
from tariffpeg.store.channels import ChannelStore
from tariffpeg.store.db import Database
from tariffpeg.store.licences import LicenceStore
from tariffpeg.store.listings import COLUMNS, ListingStore, flatten
from tests.store.conftest import a_channel, a_licence


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


@pytest.fixture
def store(stocked: Database) -> ListingStore:
    ChannelStore(stocked).add(a_channel("quayside"))
    LicenceStore(stocked).add(a_licence(5000))
    return ListingStore(stocked)


def test_flattening_produces_one_value_for_every_column() -> None:
    assert len(flatten(listing())) == len(COLUMNS)


def test_a_listing_round_trips_through_the_register(store: ListingStore) -> None:
    original = listing(note="confirmed against the address on the plaque")
    store.add(original)
    assert store.get(4021, "seaboard") == original


def test_the_same_premises_on_the_same_channel_twice_is_refused(store: ListingStore) -> None:
    store.add(listing())
    with pytest.raises(AlreadyExists, match="listing"):
        store.add(listing(path="/property/other"))


def test_two_licences_pointed_at_one_page_is_refused(store: ListingStore) -> None:
    store.add(listing())
    with pytest.raises(AlreadyExists, match="property"):
        store.add(listing(licence_serial=5000))


def test_the_same_property_reference_on_another_channel_is_fine(store: ListingStore) -> None:
    store.add(listing())
    store.add(listing(channel="quayside"))
    assert len(store.for_licence(4021)) == 2


def test_asking_for_a_listing_nobody_recorded_is_refused(store: ListingStore) -> None:
    with pytest.raises(NotFound, match="listing"):
        store.get(4021, "seaboard")


def test_a_listing_can_be_written_over(store: ListingStore) -> None:
    store.add(listing())
    store.replace(listing(path="/property/anchor/reviews", note="the channel moved the page"))
    reread = store.get(4021, "seaboard")
    assert reread.path == "/property/anchor/reviews"
    assert "moved the page" in reread.note


def test_replacing_a_listing_nobody_recorded_is_refused(store: ListingStore) -> None:
    with pytest.raises(NotFound):
        store.replace(listing())


def test_retired_listings_are_left_out_unless_they_are_asked_for(store: ListingStore) -> None:
    store.add(listing())
    store.add(listing(channel="quayside"))
    store.replace(store.get(4021, "quayside").retired("the channel took the page down"))
    assert [item.channel for item in store.for_licence(4021)] == ["seaboard"]
    assert len(store.for_licence(4021, active_only=False)) == 2


def test_listings_can_be_read_a_channel_at_a_time(store: ListingStore) -> None:
    store.add(listing())
    store.add(listing(licence_serial=5000, property_ref="P-99000"))
    assert [item.licence_serial for item in store.on_channel("seaboard")] == [4021, 5000]
    assert store.on_channel("quayside") == ()


def test_a_retired_listing_is_left_out_of_the_channel_listing(store: ListingStore) -> None:
    store.add(listing())
    store.replace(store.get(4021, "seaboard").retired("gone for good"))
    assert store.on_channel("seaboard") == ()
    assert len(store.on_channel("seaboard", active_only=False)) == 1


def test_the_stale_listings_are_the_ones_nobody_has_looked_at(store: ListingStore) -> None:
    store.add(listing(confirmed_on=dt.date(2025, 4, 1)))
    store.add(listing(channel="quayside", confirmed_on=dt.date(2026, 8, 1)))
    stale = store.stale_on(dt.date(2026, 11, 1))
    assert [item.channel for item in stale] == ["seaboard"]
    assert store.stale_on(dt.date(2025, 5, 1)) == ()


def test_a_retired_listing_never_shows_up_as_stale(store: ListingStore) -> None:
    store.add(listing(confirmed_on=dt.date(2020, 4, 1)))
    store.replace(store.get(4021, "seaboard").retired("gone for good"))
    assert store.stale_on(dt.date(2026, 11, 1)) == ()


def test_a_listing_can_be_taken_off_the_register(store: ListingStore) -> None:
    store.add(listing())
    store.remove(4021, "seaboard")
    assert not store.exists(4021, "seaboard")
    with pytest.raises(NotFound):
        store.remove(4021, "seaboard")


def test_dropping_a_licence_takes_its_listings_with_it(
    store: ListingStore, stocked: Database
) -> None:
    store.add(listing())
    LicenceStore(stocked).remove(4021)
    assert store.on_channel("seaboard", active_only=False) == ()
