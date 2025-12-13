"""Two copies of one guest is one guest, and treating it as two schedules an inspection."""

from __future__ import annotations

import pytest

from tariffpeg.dedupe.syndication import (
    DEFAULT_RULES,
    Cluster,
    SyndicationRules,
    Verdict,
    compare,
    group,
)
from tariffpeg.errors import Invalid
from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.model.period import StayMonth
from tariffpeg.model.review import Review

AGENT = "tariffpeg-harvester (standards@example-authority.test)"
DIGEST = "sha256:" + "a" * 64
ORIGINAL = (
    "The lift was out of order for the whole week we were there and nobody at "
    "the front desk mentioned it when we arrived."
)
TRIMMED = (
    "The lift was out of order for the whole week we were there and nobody at "
    "the front desk mentioned it"
)
DIFFERENT = (
    "Breakfast was not included in the rate we paid and we were charged twelve "
    "pounds each on the last morning of our stay."
)


def channel(slug: str, syndication: SyndicationClass = SyndicationClass.PRIMARY) -> Channel:
    return Channel(
        slug=slug,
        name=slug.title(),
        base_url=f"https://{slug}.example",
        syndication=syndication,
        policy=FetchPolicy(AGENT, 1500, 400),
    )


CHANNELS = {
    "seaboard": channel("seaboard"),
    "quayside": channel("quayside"),
    "atlas": channel("atlas", SyndicationClass.AGGREGATOR),
    "mirrored": channel("mirrored", SyndicationClass.MIRROR),
}


def review(channel_slug: str, number: str, body: str = ORIGINAL, **over: object) -> Review:
    base: dict[str, object] = {
        "channel": channel_slug,
        "channel_review_id": number,
        "licence_serial": 4021,
        "stay": StayMonth(2025, 7),
        "unit_points": 74,
        "raw_score": "8.4",
        "body": body,
        "capture_digest": DIGEST,
        "profile_key": f"{channel_slug}/v1",
    }
    base.update(over)
    return Review(**base)  # type: ignore[arg-type]


def test_a_review_is_the_same_as_itself() -> None:
    one = review("seaboard", "1")
    assert compare(one, one, CHANNELS) is Verdict.SAME


def test_reviews_of_two_different_licences_are_never_the_same() -> None:
    left = review("seaboard", "1")
    right = review("atlas", "1", licence_serial=9999)
    assert compare(left, right, CHANNELS) is Verdict.DIFFERENT


def test_reviews_of_different_stay_months_are_different_however_alike_they_read() -> None:
    left = review("seaboard", "1")
    right = review("atlas", "2", stay=StayMonth(2025, 8))
    assert compare(left, right, CHANNELS) is Verdict.DIFFERENT


def test_a_month_tolerance_can_be_widened_when_the_unit_says_so() -> None:
    left = review("seaboard", "1")
    right = review("atlas", "2", stay=StayMonth(2025, 8))
    rules = SyndicationRules(month_tolerance=1)
    assert compare(left, right, CHANNELS, rules) is Verdict.SAME


def test_reviews_about_different_matters_are_different_reviews() -> None:
    left = review("seaboard", "1")
    right = review("atlas", "2", body=DIFFERENT)
    assert compare(left, right, CHANNELS) is Verdict.DIFFERENT


def test_an_aggregator_carrying_a_trimmed_copy_is_the_same_review() -> None:
    left = review("seaboard", "1")
    right = review("atlas", "77", body=TRIMMED)
    assert compare(left, right, CHANNELS) is Verdict.SAME


def test_a_mirror_carrying_the_same_words_is_the_same_review() -> None:
    left = review("seaboard", "1")
    right = review("mirrored", "77")
    assert compare(left, right, CHANNELS) is Verdict.SAME


def test_two_primary_channels_with_the_same_words_are_only_likely() -> None:
    left = review("seaboard", "1")
    right = review("quayside", "77")
    assert compare(left, right, CHANNELS) is Verdict.LIKELY


def test_the_same_channel_twice_is_only_likely_because_channels_do_not_repeat() -> None:
    left = review("seaboard", "1")
    right = review("seaboard", "2")
    assert compare(left, right, CHANNELS) is Verdict.LIKELY


def test_scores_too_far_apart_stop_short_of_the_same_review() -> None:
    left = review("seaboard", "1")
    right = review("atlas", "77", unit_points=30)
    assert compare(left, right, CHANNELS) is Verdict.LIKELY


def test_a_partial_overlap_stops_short_of_the_same_review() -> None:
    partial = ORIGINAL.split(" and ")[0] + " and we told them on the second day."
    left = review("seaboard", "1")
    right = review("atlas", "77", body=partial)
    assert compare(left, right, CHANNELS) is not Verdict.SAME


def test_a_channel_the_register_has_forgotten_cannot_be_a_reproducer() -> None:
    left = review("seaboard", "1")
    right = review("atlas", "77")
    assert compare(left, right, {"seaboard": CHANNELS["seaboard"]}) is Verdict.LIKELY


def test_thresholds_that_do_not_climb_in_order_are_refused() -> None:
    with pytest.raises(Invalid, match="climb from nought to one"):
        SyndicationRules(same_threshold=0.4, likely_threshold=0.6)
    with pytest.raises(Invalid, match="climb from nought to one"):
        SyndicationRules(same_threshold=1.4)


def test_a_negative_tolerance_is_refused() -> None:
    with pytest.raises(Invalid, match="not negative"):
        SyndicationRules(score_tolerance=-1)
    with pytest.raises(Invalid, match="not negative"):
        SyndicationRules(month_tolerance=-1)


def test_unrelated_reviews_each_get_their_own_cluster() -> None:
    reviews = [review("seaboard", "1"), review("quayside", "2", body=DIFFERENT)]
    clusters = group(reviews, CHANNELS)
    assert len(clusters) == 2
    assert all(cluster.size == 1 for cluster in clusters)


def test_copies_of_one_opinion_land_in_one_cluster() -> None:
    reviews = [
        review("seaboard", "1"),
        review("atlas", "77", body=TRIMMED),
        review("mirrored", "5"),
    ]
    clusters = group(reviews, CHANNELS)
    assert len(clusters) == 1
    assert clusters[0].size == 3
    assert clusters[0].channels() == ("atlas", "mirrored", "seaboard")
    assert clusters[0].is_syndicated()


def test_a_cluster_of_one_is_not_syndicated() -> None:
    clusters = group([review("seaboard", "1")], CHANNELS)
    assert not clusters[0].is_syndicated()
    assert clusters[0].channels() == ("seaboard",)


def test_only_the_channels_that_collect_their_own_count_as_independent() -> None:
    reviews = [review("seaboard", "1"), review("atlas", "77"), review("quayside", "5")]
    cluster = group(reviews, CHANNELS)[0]
    assert cluster.independent_channels(CHANNELS) == ("quayside", "seaboard")


def test_the_quoted_copy_is_stable_across_runs() -> None:
    reviews = [review("quayside", "9"), review("seaboard", "1"), review("atlas", "77")]
    assert group(reviews, CHANNELS)[0].leader.key == "atlas:77"
    assert group(list(reversed(reviews)), CHANNELS)[0].leader.key == "atlas:77"


def test_grouping_an_empty_set_gives_back_no_clusters() -> None:
    assert group([], CHANNELS) == ()


def test_a_cluster_with_nothing_in_it_is_refused() -> None:
    with pytest.raises(Invalid, match="at least one review"):
        Cluster(())


def test_the_published_thresholds_are_the_default() -> None:
    assert DEFAULT_RULES.same_threshold > DEFAULT_RULES.likely_threshold
