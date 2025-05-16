"""Guessing which block a loose review object belongs to puts a quote under the wrong licence."""

from __future__ import annotations

from dataclasses import replace

from tariffpeg.parse.dom import parse
from tariffpeg.parse.extract import RawReview, extract
from tariffpeg.parse.profile import FieldRule, Profile

STRUCTURED = """
<script type="application/ld+json">
{"@type": "LodgingBusiness", "review": [
  {"@type": "Review", "identifier": "91188", "name": "Lovely spot",
   "reviewBody": "The lift was out all week and nobody said.", "inLanguage": "en"},
  {"@type": "Review", "identifier": "91190", "name": "Bien",
   "reviewBody": "No breakfast was served at all.", "inLanguage": "fr"}
]}
</script>
"""


def with_structured(profile: Profile, prefer: bool = False) -> Profile:
    fields = (
        *profile.fields,
        FieldRule("language", "structured", key="inLanguage"),
        FieldRule("response", "structured", key="reviewBody"),
    )
    return replace(profile, fields=fields, prefer_structured=prefer)


def test_a_page_gives_up_one_review_per_container(markup: str, profile: Profile) -> None:
    found = extract(profile, parse(markup))
    assert found.blocks_seen == 2
    assert found.yielded == 2
    assert not found.empty
    assert found.dropped == ()


def test_each_field_is_read_the_way_the_profile_says(markup: str, profile: Profile) -> None:
    first = extract(profile, parse(markup)).reviews[0]
    assert first.get("channel_review_id") == "91188"
    assert first.get("title") == "Lovely spot"
    assert first.get("body") == "The lift was out all week."
    assert first.get("score") == "8.4"
    assert first.get("stay_month") == "June 2025"
    assert first.get("room_class", "unknown") == "unknown"


def test_the_profile_that_read_the_page_is_recorded_on_every_review(
    markup: str, profile: Profile
) -> None:
    for review in extract(profile, parse(markup)).reviews:
        assert review.profile_key == "seaboard/v1"


def test_the_position_on_the_page_is_kept(markup: str, profile: Profile) -> None:
    assert [review.position for review in extract(profile, parse(markup)).reviews] == [0, 1]


def test_a_block_missing_a_required_field_is_dropped_and_named(profile: Profile) -> None:
    page = '<article class="review" data-id="1"><h3 class="title">t</h3></article>'
    found = extract(profile, parse(page))
    assert found.blocks_seen == 1
    assert found.yielded == 0
    assert found.empty
    assert found.dropped == ("block 0 had no body or score",)


def test_a_page_with_no_containers_gives_up_nothing(profile: Profile) -> None:
    found = extract(profile, parse("<div><p>no reviews yet</p></div>"))
    assert found.blocks_seen == 0
    assert found.empty


def test_the_link_to_the_next_page_is_read(markup: str, profile: Profile) -> None:
    assert extract(profile, parse(markup)).next_page == "/p/1/reviews?page=2"


def test_the_next_page_link_is_made_absolute_against_the_page_it_came_from(
    markup: str, profile: Profile
) -> None:
    found = extract(profile, parse(markup), "https://seaboard.example/p/1/reviews")
    assert found.next_page == "https://seaboard.example/p/1/reviews?page=2"


def test_a_page_with_no_next_link_says_so(markup: str, profile: Profile) -> None:
    found = extract(profile, parse(markup.replace('class="next"', 'class="prev"')))
    assert found.next_page == ""


def test_a_profile_with_no_next_rule_never_looks_for_one(markup: str, profile: Profile) -> None:
    assert extract(replace(profile, next_page=""), parse(markup)).next_page == ""


def test_structured_values_fill_gaps_the_markup_left(markup: str, profile: Profile) -> None:
    found = extract(with_structured(profile), parse(markup + STRUCTURED))
    assert [review.get("language") for review in found.reviews] == ["en", "fr"]


def test_the_markup_wins_by_default_where_both_copies_say_something(
    markup: str, profile: Profile
) -> None:
    widened = replace(
        with_structured(profile),
        fields=(
            *profile.fields[:2],
            FieldRule("body", "text", "p.body", required=True),
            profile.fields[3],
            FieldRule("response", "structured", key="reviewBody"),
        ),
    )
    found = extract(widened, parse(markup + STRUCTURED))
    assert found.reviews[0].get("body") == "The lift was out all week."
    assert found.reviews[0].get("response").endswith("nobody said.")


def test_a_profile_that_prefers_the_structured_copy_gets_it(markup: str, profile: Profile) -> None:
    without_title = tuple(rule for rule in profile.fields if rule.name != "title")
    preferring = replace(
        profile,
        prefer_structured=True,
        fields=(*without_title, FieldRule("title", "structured", key="reviewBody")),
    )
    found = extract(preferring, parse(markup + STRUCTURED))
    assert found.reviews[0].get("title").endswith("nobody said.")


def test_blocks_and_objects_are_matched_on_the_channel_review_id(
    markup: str, profile: Profile
) -> None:
    shuffled = STRUCTURED.replace("91188", "ZZZ").replace("91190", "91188").replace("ZZZ", "91190")
    found = extract(with_structured(profile), parse(markup + shuffled))
    assert [review.get("language") for review in found.reviews] == ["fr", "en"]


def test_a_structured_object_that_matches_no_block_is_reported(
    markup: str, profile: Profile
) -> None:
    orphan = STRUCTURED.replace("91190", "99999")
    found = extract(with_structured(profile), parse(markup + orphan))
    assert any("did not match a block" in note for note in found.notes)


def test_objects_with_no_id_are_folded_in_by_position_when_the_counts_agree(
    markup: str, profile: Profile
) -> None:
    anonymous = STRUCTURED.replace('"identifier": "91188",', "").replace(
        '"identifier": "91190",', ""
    )
    found = extract(with_structured(profile), parse(markup + anonymous))
    assert [review.get("language") for review in found.reviews] == ["en", "fr"]


def test_objects_with_no_id_are_left_alone_when_the_counts_disagree(
    markup: str, profile: Profile
) -> None:
    one = """
    <script type="application/ld+json">
    {"@type": "Review", "reviewBody": "only one of these", "inLanguage": "de"}
    </script>
    """
    found = extract(with_structured(profile), parse(markup + one))
    assert [review.get("language") for review in found.reviews] == ["", ""]
    assert any("none were folded in" in note for note in found.notes)


def test_a_broken_structured_block_is_reported_and_the_markup_still_reads(
    markup: str, profile: Profile
) -> None:
    broken = '<script type="application/ld+json">{"@type": "Review"</script>'
    found = extract(with_structured(profile), parse(markup + broken))
    assert found.yielded == 2
    assert any("is not json" in note for note in found.notes)


def test_a_raw_review_reports_what_it_is_missing() -> None:
    review = RawReview({"body": "words"}, "seaboard/v1")
    assert review.missing() == ("channel_review_id", "score")
    assert not review.complete()
    assert RawReview({"channel_review_id": "1", "body": "w", "score": "8"}, "k").complete()
