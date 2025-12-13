"""A builder that waits for the closing tag nests forty reviews inside the first one."""

from __future__ import annotations

from tariffpeg.parse.dom import Element, TextNode, parse


def test_a_plain_tree_has_the_shape_of_the_page_it_came_from() -> None:
    root = parse("<div><p>hello</p></div>")
    assert root.tag == "[document]"
    div = root.elements()[0]
    assert div.tag == "div"
    assert div.elements()[0].tag == "p"
    assert div.text() == "hello"


def test_text_hangs_off_the_element_it_was_written_in() -> None:
    root = parse("<div>before<p>inside</p>after</div>")
    div = root.elements()[0]
    assert [type(child).__name__ for child in div.children] == [
        "TextNode",
        "Element",
        "TextNode",
    ]
    assert div.text() == "beforeinsideafter"


def test_text_can_be_joined_with_a_separator_for_reading() -> None:
    root = parse("<div><span>one</span><span>two</span></div>")
    assert root.elements()[0].text(" ") == "one two"


def test_the_text_of_an_empty_element_is_empty() -> None:
    assert parse("<div></div>").elements()[0].text() == ""


def test_an_unclosed_paragraph_is_closed_by_the_next_one() -> None:
    root = parse("<div><p>one<p>two</div>")
    div = root.elements()[0]
    assert [p.text() for p in div.elements()] == ["one", "two"]


def test_an_unclosed_paragraph_is_closed_by_a_block_that_follows() -> None:
    root = parse("<div><p>one<ul><li>two</ul></div>")
    div = root.elements()[0]
    assert [child.tag for child in div.elements()] == ["p", "ul"]


def test_a_span_after_an_open_paragraph_stays_inside_it() -> None:
    root = parse("<div><p>one<span>two</span></div>")
    paragraph = root.elements()[0].elements()[0]
    assert paragraph.tag == "p"
    assert [child.tag for child in paragraph.elements()] == ["span"]


def test_unclosed_list_items_become_siblings_and_not_a_ladder() -> None:
    root = parse("<ul><li>one<li>two<li>three</ul>")
    items = root.elements()[0].elements()
    assert [item.text() for item in items] == ["one", "two", "three"]
    assert all(item.tag == "li" for item in items)


def test_unclosed_table_cells_become_siblings() -> None:
    root = parse("<table><tr><td>a<td>b<tr><td>c</table>")
    rows = root.find_all("tr")
    assert len(rows) == 2
    assert [cell.text() for cell in rows[0].find_all("td")] == ["a", "b"]
    assert [cell.text() for cell in rows[1].find_all("td")] == ["c"]


def test_definition_lists_close_each_other() -> None:
    root = parse("<dl><dt>term<dd>meaning<dt>other</dl>")
    assert [child.tag for child in root.elements()[0].elements()] == ["dt", "dd", "dt"]


def test_a_void_tag_never_swallows_what_comes_after_it() -> None:
    root = parse("<div><img src='/a.png'>after</div>")
    div = root.elements()[0]
    assert div.elements()[0].tag == "img"
    assert div.text() == "after"


def test_a_stray_closing_tag_with_nothing_open_is_ignored() -> None:
    root = parse("</span><p>text</p>")
    assert [child.tag for child in root.elements()] == ["p"]


def test_a_closing_tag_closes_the_matching_ancestor_and_everything_under_it() -> None:
    root = parse("<div><span><b>text</div><p>after</p>")
    assert [child.tag for child in root.elements()] == ["div", "p"]


def test_tags_left_open_at_the_end_of_the_page_still_hold_their_text() -> None:
    root = parse("<div><p>unfinished")
    assert root.elements()[0].elements()[0].text() == "unfinished"


def test_attributes_read_off_an_element_the_way_they_do_off_a_tag() -> None:
    element = parse('<a href="/p/1" class="card wide" id="first">x</a>').elements()[0]
    assert element.get("href") == "/p/1"
    assert element.classes() == ("card", "wide")
    assert element.node_id() == "first"
    assert element.has("href")
    assert not element.has("rel")
    assert element.get("rel", "none") == "none"


def test_an_element_with_no_id_reports_an_empty_one() -> None:
    assert parse("<div>x</div>").elements()[0].node_id() == ""


def test_descendants_come_back_in_document_order() -> None:
    root = parse("<div><a><b></b></a><c></c></div>")
    assert [node.tag for node in root.descendants()] == ["div", "a", "b", "c"]


def test_ancestors_come_back_nearest_first() -> None:
    root = parse("<div><section><p>x</p></section></div>")
    paragraph = root.find("p")
    assert paragraph is not None
    assert [node.tag for node in paragraph.ancestors()] == ["section", "div", "[document]"]
    assert paragraph.depth() == 3


def test_the_root_has_no_ancestors() -> None:
    root = parse("<p>x</p>")
    assert root.ancestors() == []
    assert root.depth() == 0


def test_finding_by_tag_returns_the_first_and_the_whole_set() -> None:
    root = parse("<ul><li>one</li><li>two</li></ul>")
    first = root.find("li")
    assert first is not None
    assert first.text() == "one"
    assert len(root.find_all("li")) == 2
    assert root.find("table") is None
    assert root.find_all("table") == ()


def test_a_child_points_back_at_its_parent() -> None:
    root = parse("<div><p>x</p></div>")
    paragraph = root.find("p")
    assert paragraph is not None
    assert paragraph.parent is not None
    assert paragraph.parent.tag == "div"


def test_appending_a_node_by_hand_wires_the_parent_up() -> None:
    parent = Element("div")
    child = TextNode("text")
    parent.append(child)
    assert child.parent is parent
    assert parent.text() == "text"
    assert child.text() == "text"


def test_script_contents_do_not_become_elements() -> None:
    root = parse("<div><script>var a = '<p>x</p>';</script></div>")
    assert root.find("p") is None
    script = root.find("script")
    assert script is not None
    assert "var a" in script.text()
