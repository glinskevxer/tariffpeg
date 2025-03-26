"""The rule that wins is the longest one, not the first one."""

from __future__ import annotations

from tariffpeg.fetch.robots import (
    ALLOW_EVERYTHING,
    ALLOW_NOTHING,
    MAX_BYTES,
    Group,
    Robots,
    Rule,
    parse,
)

AGENT = "tariffpeg-harvester"


def test_a_missing_file_forbids_nothing() -> None:
    assert ALLOW_EVERYTHING.allows(AGENT, "/anything")
    assert ALLOW_EVERYTHING.crawl_delay_ms(AGENT) is None


def test_a_file_that_could_not_be_served_is_not_permission() -> None:
    assert not ALLOW_NOTHING.allows(AGENT, "/anything")


def test_an_empty_file_forbids_nothing() -> None:
    assert parse("").allows(AGENT, "/property/1/reviews")


def test_a_blanket_disallow_stops_everything() -> None:
    robots = parse("User-agent: *\nDisallow: /")
    assert not robots.allows(AGENT, "/")
    assert not robots.allows(AGENT, "/property/1")


def test_an_empty_disallow_value_is_not_a_rule_at_all() -> None:
    robots = parse("User-agent: *\nDisallow:")
    assert robots.allows(AGENT, "/property/1")
    assert robots.groups[0].rules == ()


def test_the_longest_matching_rule_wins_and_not_the_first_one() -> None:
    robots = parse("User-agent: *\nDisallow: /property\nAllow: /property/*/reviews")
    assert not robots.allows(AGENT, "/property/1")
    assert robots.allows(AGENT, "/property/1/reviews")


def test_the_longest_rule_wins_even_when_the_disallow_comes_last() -> None:
    robots = parse("User-agent: *\nAllow: /property/*/reviews\nDisallow: /property")
    assert robots.allows(AGENT, "/property/1/reviews")


def test_an_allow_beats_a_disallow_of_the_same_length() -> None:
    robots = parse("User-agent: *\nDisallow: /reviews\nAllow: /reviews")
    assert robots.allows(AGENT, "/reviews/1")


def test_a_star_in_a_pattern_matches_any_run_of_characters() -> None:
    robots = parse("User-agent: *\nDisallow: /*/print")
    assert not robots.allows(AGENT, "/property/print")
    assert not robots.allows(AGENT, "/a/b/print")
    assert robots.allows(AGENT, "/property/reviews")


def test_a_dollar_anchors_the_pattern_to_the_end_of_the_path() -> None:
    robots = parse("User-agent: *\nDisallow: /*.pdf$")
    assert not robots.allows(AGENT, "/brochure.pdf")
    assert robots.allows(AGENT, "/brochure.pdf.html")


def test_a_pattern_matches_from_the_start_of_the_path() -> None:
    robots = parse("User-agent: *\nDisallow: /print")
    assert not robots.allows(AGENT, "/print/page")
    assert robots.allows(AGENT, "/property/print")


def test_a_named_group_beats_the_catch_all() -> None:
    robots = parse(
        "User-agent: *\nDisallow: /\n\nUser-agent: tariffpeg-harvester\nAllow: /\nDisallow: /admin"
    )
    assert robots.allows(AGENT, "/property/1")
    assert not robots.allows(AGENT, "/admin/users")
    assert not robots.allows("someone-else", "/property/1")


def test_the_longest_matching_agent_name_wins() -> None:
    robots = parse(
        "User-agent: tariffpeg\nDisallow: /\n\nUser-agent: tariffpeg-harvester\nAllow: /\n"
    )
    assert robots.allows("tariffpeg-harvester/1.0", "/property/1")
    assert not robots.allows("tariffpeg-other", "/property/1")


def test_a_group_that_names_us_and_says_nothing_still_silences_the_catch_all() -> None:
    robots = parse("User-agent: *\nDisallow: /\n\nUser-agent: tariffpeg-harvester\n")
    assert robots.allows(AGENT, "/property/1")


def test_two_agent_lines_in_a_row_share_one_block_of_rules() -> None:
    robots = parse("User-agent: alpha\nUser-agent: beta\nDisallow: /x")
    assert len(robots.groups) == 1
    assert robots.groups[0].agents == ("alpha", "beta")
    assert not robots.allows("beta", "/x")
    assert not robots.allows("alpha", "/x")


def test_agent_matching_ignores_case_on_both_sides() -> None:
    robots = parse("User-Agent: TariffPeg-Harvester\nDisallow: /x")
    assert not robots.allows("tariffpeg-harvester", "/x")


def test_a_crawl_delay_is_read_in_seconds_and_kept_in_milliseconds() -> None:
    robots = parse("User-agent: *\nCrawl-delay: 2.5")
    assert robots.crawl_delay_ms(AGENT) == 2500
    assert parse("User-agent: *\nCrawl-delay: 10").crawl_delay_ms(AGENT) == 10000


def test_a_crawl_delay_that_is_not_a_number_is_ignored() -> None:
    assert parse("User-agent: *\nCrawl-delay: soon").crawl_delay_ms(AGENT) is None
    assert parse("User-agent: *\nCrawl-delay: -3").crawl_delay_ms(AGENT) is None


def test_a_crawl_delay_belongs_to_the_group_that_carries_it() -> None:
    robots = parse(
        "User-agent: *\nCrawl-delay: 1\n\nUser-agent: tariffpeg-harvester\nCrawl-delay: 30"
    )
    assert robots.crawl_delay_ms(AGENT) == 30000
    assert robots.crawl_delay_ms("someone-else") == 1000


def test_sitemap_lines_are_collected_from_anywhere_in_the_file() -> None:
    robots = parse(
        "Sitemap: https://seaboard.example/sitemap.xml\n"
        "User-agent: *\nDisallow: /admin\n"
        "Sitemap: https://seaboard.example/sitemap-2.xml"
    )
    assert robots.sitemaps == (
        "https://seaboard.example/sitemap.xml",
        "https://seaboard.example/sitemap-2.xml",
    )


def test_comments_and_junk_lines_are_ignored() -> None:
    robots = parse("# a comment\nUser-agent: *  # us\nDisallow: /admin # not this\nnonsense\n")
    assert not robots.allows(AGENT, "/admin")
    assert robots.allows(AGENT, "/property")


def test_a_file_past_the_size_limit_is_treated_as_unreadable() -> None:
    robots = parse("User-agent: *\nDisallow:\n" + "# padding\n" * (MAX_BYTES // 5))
    assert robots.unparseable
    assert not robots.allows(AGENT, "/anything")


def test_a_group_with_no_matching_rule_allows_the_path() -> None:
    group = Group(("*",), (Rule(False, "/admin"),))
    assert group.allows("/property")
    assert group.best_rule("/property") is None


def test_a_file_with_no_group_for_us_allows_everything() -> None:
    robots = Robots((Group(("otherbot",), (Rule(False, "/"),)),))
    assert robots.group_for(AGENT) is None
    assert robots.allows(AGENT, "/property")


def test_the_source_snippet_is_kept_for_the_evidence_file_but_not_compared() -> None:
    one = parse("User-agent: *\nDisallow: /a")
    two = parse("User-agent: *\nDisallow: /a\n# and a comment nobody cares about")
    assert one.source != two.source
    assert one == two
