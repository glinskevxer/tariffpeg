"""Channels serve markup no validator would accept, and it still has to be read."""

from __future__ import annotations

from tariffpeg.parse.tokens import (
    Comment,
    Doctype,
    EndTag,
    StartTag,
    Text,
    tokenize,
)


def tags(source: str) -> list[str]:
    return [t.name for t in tokenize(source) if isinstance(t, StartTag)]


def texts(source: str) -> list[str]:
    return [t.data for t in tokenize(source) if isinstance(t, Text) and not t.is_blank()]


def test_a_plain_page_breaks_into_tags_and_text() -> None:
    found = tokenize("<p>hello</p>")
    assert found == [StartTag("p"), Text("hello"), EndTag("p")]


def test_text_before_any_tag_is_kept() -> None:
    assert texts("leading<p>x</p>") == ["leading", "x"]


def test_text_after_the_last_tag_is_kept() -> None:
    assert texts("<p>x</p>trailing") == ["x", "trailing"]


def test_tag_names_are_lowercased_on_both_ends() -> None:
    assert tokenize("<DIV></DIV>") == [StartTag("div"), EndTag("div")]


def test_a_quoted_attribute_is_read_with_its_value() -> None:
    tag = tokenize('<a href="/p/1" class="card">')[0]
    assert isinstance(tag, StartTag)
    assert tag.get("href") == "/p/1"
    assert tag.classes() == ("card",)


def test_an_attribute_quoted_with_apostrophes_is_read_the_same_way() -> None:
    tag = tokenize("<a href='/p/1'>")[0]
    assert isinstance(tag, StartTag)
    assert tag.get("href") == "/p/1"


def test_an_unquoted_attribute_is_read_up_to_the_whitespace() -> None:
    tag = tokenize("<a href=/p/1 rel=next>")[0]
    assert isinstance(tag, StartTag)
    assert tag.get("href") == "/p/1"
    assert tag.get("rel") == "next"


def test_an_attribute_with_no_value_reads_as_an_empty_string() -> None:
    tag = tokenize("<input disabled>")[0]
    assert isinstance(tag, StartTag)
    assert tag.has("disabled")
    assert tag.get("disabled") == ""
    assert not tag.has("checked")
    assert tag.get("checked", "no") == "no"


def test_attribute_names_are_lowercased_and_values_are_not() -> None:
    tag = tokenize('<a HREF="/P/1">')[0]
    assert isinstance(tag, StartTag)
    assert tag.get("href") == "/P/1"


def test_a_repeated_attribute_keeps_the_first_value_the_way_a_browser_does() -> None:
    tag = tokenize('<a href="/first" href="/second">')[0]
    assert isinstance(tag, StartTag)
    assert tag.get("href") == "/first"


def test_entities_are_decoded_in_text_and_in_attribute_values() -> None:
    assert texts("<p>caf&eacute; &amp; bar</p>") == ["caf\u00e9 & bar"]
    tag = tokenize('<a title="caf&eacute;">')[0]
    assert isinstance(tag, StartTag)
    assert tag.get("title") == "caf\u00e9"


def test_a_void_tag_is_self_closing_whatever_the_page_writes() -> None:
    for source in ("<br>", "<br/>", "<br />"):
        tag = tokenize(source)[0]
        assert isinstance(tag, StartTag)
        assert tag.self_closing


def test_a_self_closing_ordinary_tag_is_marked_as_one() -> None:
    closed = tokenize("<div/>")[0]
    plain = tokenize("<div>")[0]
    assert isinstance(closed, StartTag)
    assert isinstance(plain, StartTag)
    assert closed.self_closing
    assert not plain.self_closing


def test_a_comment_is_kept_because_review_ids_hide_in_them() -> None:
    found = tokenize("<div><!-- review 91188 --></div>")
    assert Comment(" review 91188 ") in found


def test_a_comment_that_is_never_closed_takes_the_rest_of_the_page() -> None:
    found = tokenize("<div><!-- unfinished")
    assert found[-1] == Comment(" unfinished")


def test_a_doctype_is_kept_so_the_page_can_be_identified() -> None:
    found = tokenize("<!DOCTYPE html><html>")
    assert found[0] == Doctype("DOCTYPE html")


def test_a_stray_less_than_sign_in_a_review_is_text_and_not_a_tag() -> None:
    assert texts("<p>rooms < 3 were noisy</p>") == ["rooms < 3 were noisy"]


def test_runs_of_text_split_by_a_stray_sign_are_joined_back_into_one() -> None:
    found = tokenize("<p>a < b < c</p>")
    assert [t for t in found if isinstance(t, Text)] == [Text("a < b < c")]


def test_a_tag_that_is_never_closed_does_not_lose_the_attributes_before_it() -> None:
    tag = tokenize('<a href="/p/1"')[0]
    assert isinstance(tag, StartTag)
    assert tag.get("href") == "/p/1"


def test_script_contents_are_not_scanned_for_tags() -> None:
    found = tokenize("<script>var a = 1 < 2; var b = '<div>';</script><p>after</p>")
    assert tags("<script>var a = 1 < 2;</script><p>after</p>") == ["script", "p"]
    assert any(isinstance(t, Text) and "var a" in t.data for t in found)


def test_script_contents_keep_their_entities_undecoded() -> None:
    found = tokenize("<script>a &amp;&amp; b</script>")
    assert Text("a &amp;&amp; b") in found


def test_a_style_block_is_treated_the_same_way() -> None:
    assert tags("<style>a { color: red }</style><p>x</p>") == ["style", "p"]


def test_a_raw_text_tag_that_is_never_closed_takes_the_rest_of_the_page() -> None:
    found = tokenize("<script>never finished")
    assert found[-1] == Text("never finished")


def test_an_empty_raw_text_element_yields_only_its_tags() -> None:
    assert tokenize("<script></script>") == [StartTag("script"), EndTag("script")]


def test_a_closing_tag_with_junk_after_the_name_still_closes() -> None:
    assert tokenize("</div junk>") == [EndTag("div")]


def test_a_blank_run_of_text_reports_itself_as_blank() -> None:
    assert Text("   \n ").is_blank()
    assert not Text(" x ").is_blank()


def test_an_empty_page_yields_nothing() -> None:
    assert tokenize("") == []
