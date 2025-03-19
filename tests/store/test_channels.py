"""The agreed terms are columns, because somebody is going to be asked about them."""

from __future__ import annotations

import pytest

from tariffpeg.errors import AlreadyExists, NotFound
from tariffpeg.model.channel import Channel, CourtesyWindow, FetchPolicy, SyndicationClass
from tariffpeg.store.channels import COLUMNS, ChannelStore, flatten, hydrate
from tariffpeg.store.db import Database

AGENT = "tariffpeg-harvester (standards@example-authority.test)"


def make(slug: str = "seaboard", **over: object) -> Channel:
    base: dict[str, object] = {
        "slug": slug,
        "name": "Seaboard Stays",
        "base_url": "https://seaboard.example",
        "syndication": SyndicationClass.PRIMARY,
        "policy": FetchPolicy(
            user_agent=AGENT,
            crawl_delay_ms=1500,
            daily_request_ceiling=400,
            window=CourtesyWindow(22, 6),
            max_pages_per_property=8,
        ),
        "scale_slug": "ten-point",
        "locale": "en",
    }
    base.update(over)
    return Channel(**base)  # type: ignore[arg-type]


def test_flattening_produces_one_value_for_every_column() -> None:
    assert len(flatten(make())) == len(COLUMNS)


def test_a_channel_round_trips_through_the_register(db: Database) -> None:
    store = ChannelStore(db)
    original = make()
    store.add(original)
    assert store.get("seaboard") == original


def test_the_policy_lands_in_columns_a_person_can_read(db: Database) -> None:
    ChannelStore(db).add(make())
    row = db.conn.execute(
        "SELECT crawl_delay_ms, daily_request_ceiling, window_open, window_close, max_pages"
        " FROM channel WHERE slug = 'seaboard'"
    ).fetchone()
    assert row["crawl_delay_ms"] == 1500
    assert row["daily_request_ceiling"] == 400
    assert row["window_open"] == 22
    assert row["window_close"] == 6
    assert row["max_pages"] == 8


def test_hydrating_a_row_rebuilds_the_window_and_the_policy(db: Database) -> None:
    ChannelStore(db).add(make())
    row = db.conn.execute(f"SELECT {', '.join(COLUMNS)} FROM channel").fetchone()
    channel = hydrate(row)
    assert channel.policy.window == CourtesyWindow(22, 6)
    assert channel.policy.max_pages_per_property == 8


def test_registering_the_same_slug_twice_is_refused(db: Database) -> None:
    store = ChannelStore(db)
    store.add(make())
    with pytest.raises(AlreadyExists, match="already registered"):
        store.add(make())


def test_asking_for_a_channel_that_is_not_registered_is_refused(db: Database) -> None:
    with pytest.raises(NotFound, match="channel"):
        ChannelStore(db).get("nowhere")


def test_new_terms_are_written_over_the_old_ones(db: Database) -> None:
    store = ChannelStore(db)
    store.add(make())
    slower = make(
        policy=FetchPolicy(
            user_agent=AGENT,
            crawl_delay_ms=9000,
            daily_request_ceiling=50,
            window=CourtesyWindow(1, 5),
        )
    )
    store.replace(slower)
    reread = store.get("seaboard")
    assert reread.policy.crawl_delay_ms == 9000
    assert reread.policy.daily_request_ceiling == 50
    assert reread.policy.window == CourtesyWindow(1, 5)


def test_replacing_terms_for_an_unregistered_channel_is_refused(db: Database) -> None:
    with pytest.raises(NotFound):
        ChannelStore(db).replace(make())


def test_the_register_lists_by_slug(db: Database) -> None:
    store = ChannelStore(db)
    for slug in ("seaboard", "atlas-rooms", "quayside"):
        store.add(make(slug))
    assert store.slugs() == ("atlas-rooms", "quayside", "seaboard")
    assert [channel.slug for channel in store.all()] == ["atlas-rooms", "quayside", "seaboard"]


def test_the_register_can_be_read_a_syndication_class_at_a_time(db: Database) -> None:
    store = ChannelStore(db)
    store.add(make("seaboard"))
    store.add(make("atlas-rooms", syndication=SyndicationClass.AGGREGATOR))
    store.add(make("quayside", syndication=SyndicationClass.MIRROR))
    assert [c.slug for c in store.of_class(SyndicationClass.PRIMARY)] == ["seaboard"]
    assert [c.slug for c in store.of_class(SyndicationClass.AGGREGATOR)] == ["atlas-rooms"]
    assert [c.slug for c in store.of_class(SyndicationClass.MIRROR)] == ["quayside"]


def test_a_channel_can_be_taken_off_the_register(db: Database) -> None:
    store = ChannelStore(db)
    store.add(make())
    store.remove("seaboard")
    assert not store.exists("seaboard")
    with pytest.raises(NotFound):
        store.remove("seaboard")


def test_a_channel_knows_its_dial_and_where_its_robots_file_is() -> None:
    channel = make()
    assert channel.scale.slug == "ten-point"
    assert channel.host() == "seaboard.example"
    assert channel.robots_url() == "https://seaboard.example/robots.txt"


def test_a_channel_on_a_dial_nobody_published_is_refused() -> None:
    with pytest.raises(Exception, match="no such published scale"):
        make(scale_slug="thumbs")


def test_a_channel_with_no_locale_is_refused() -> None:
    with pytest.raises(Exception, match="some language"):
        make(locale="  ")
