"""One broken script block is not a reason to lose the other four."""

from __future__ import annotations

from tariffpeg.parse.dom import Element, parse
from tariffpeg.parse.jsonld import read, text_of, types_of


def page(*blocks: str) -> Element:
    scripts = "".join(f'<script type="application/ld+json">{block}</script>' for block in blocks)
    return parse(f"<html><head>{scripts}</head><body><p>markup</p></body></html>")


def test_a_page_with_no_structured_data_reads_as_empty() -> None:
    found = read(parse("<html><body><p>nothing</p></body></html>"))
    assert found.objects() == ()
    assert found.reviews() == ()
    assert found.problems() == ()


def test_a_single_review_object_is_found() -> None:
    found = read(page('{"@type": "Review", "reviewBody": "The lift was out."}'))
    assert len(found.reviews()) == 1
    assert found.reviews()[0]["reviewBody"] == "The lift was out."


def test_a_list_at_the_top_of_a_block_is_flattened() -> None:
    found = read(page('[{"@type": "Review", "name": "a"}, {"@type": "Review", "name": "b"}]'))
    assert [review["name"] for review in found.reviews()] == ["a", "b"]


def test_a_graph_is_flattened_into_the_objects_in_it() -> None:
    block = '{"@context": "https://schema.org", "@graph": [{"@type": "Review", "name": "a"}]}'
    assert len(read(page(block)).reviews()) == 1


def test_reviews_nested_under_a_business_are_still_found() -> None:
    block = (
        '{"@type": "LodgingBusiness", "name": "The Anchor Rooms",'
        ' "review": [{"@type": "Review", "name": "a"}, {"@type": "Review", "name": "b"}]}'
    )
    found = read(page(block))
    assert len(found.reviews()) == 2
    assert len(found.of_type("LodgingBusiness")) == 1


def test_an_object_with_a_list_of_types_is_matched_on_any_of_them() -> None:
    found = read(page('{"@type": ["Thing", "Review"], "name": "a"}'))
    assert len(found.reviews()) == 1
    assert types_of({"@type": ["Thing", "Review"]}) == frozenset({"Thing", "Review"})


def test_an_object_with_no_type_is_kept_but_is_not_a_review() -> None:
    found = read(page('{"name": "a"}'))
    assert len(found.objects()) == 1
    assert found.reviews() == ()
    assert types_of({"name": "a"}) == frozenset()
    assert types_of({"@type": 7}) == frozenset()


def test_the_context_key_is_not_walked_into() -> None:
    block = '{"@context": {"@vocab": "https://schema.org/"}, "@type": "Review", "name": "a"}'
    found = read(page(block))
    assert len(found.objects()) == 1


def test_a_block_that_is_not_json_is_skipped_and_named() -> None:
    found = read(page('{"@type": "Review"', '{"@type": "Review", "name": "good"}'))
    assert len(found.reviews()) == 1
    assert len(found.problems()) == 1
    assert "block 0 is not json" in found.problems()[0]


def test_an_empty_block_is_skipped_and_named() -> None:
    found = read(page("   "))
    assert found.problems() == ("block 0 is empty",)
    assert not found.blocks[0].ok


def test_a_block_that_parsed_reports_itself_as_fine() -> None:
    found = read(page('{"@type": "Review"}'))
    assert found.blocks[0].ok
    assert found.blocks[0].index == 0


def test_a_script_without_the_structured_data_type_is_not_read() -> None:
    markup = '<html><head><script>{"@type": "Review"}</script></head></html>'
    assert read(parse(markup)).objects() == ()


def test_a_plain_string_value_comes_back_stripped() -> None:
    assert text_of("  Lovely spot  ") == "Lovely spot"


def test_a_number_comes_back_as_its_own_text() -> None:
    assert text_of(8) == "8"
    assert text_of(8.4) == "8.4"


def test_a_nested_object_is_unwrapped_by_the_key_channels_use() -> None:
    assert text_of({"@type": "Person", "name": "Ada"}) == "Ada"
    assert text_of({"@value": "8.4"}) == "8.4"
    assert text_of({"value": "8.4"}) == "8.4"
    assert text_of({"text": "body"}) == "body"


def test_an_object_with_nothing_readable_in_it_comes_back_empty() -> None:
    assert text_of({"@type": "Person"}) == ""
    assert text_of(None) == ""


def test_a_list_gives_back_the_first_entry_that_says_anything() -> None:
    assert text_of([{"@type": "Person"}, "Ada"]) == "Ada"
    assert text_of([]) == ""


def test_several_blocks_on_one_page_are_all_read() -> None:
    found = read(
        page(
            '{"@type": "Review", "name": "a"}',
            '{"@type": "Review", "name": "b"}',
            '{"@type": "LodgingBusiness", "name": "c"}',
        )
    )
    assert len(found.blocks) == 3
    assert [review["name"] for review in found.reviews()] == ["a", "b"]


def test_a_block_that_parsed_carries_its_objects() -> None:
    from tariffpeg.parse.jsonld import Block, Structured

    block = Block(0, ({"@type": "Review"},))
    assert block.ok
    assert Structured((block,)).blocks[0] is block
