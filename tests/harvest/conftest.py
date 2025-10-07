"""A profile and a page of markup the harvest tests fetch."""

from __future__ import annotations

import pytest

from tariffpeg.parse.profile import FieldRule, Profile

REVIEWS = (
    (
        "91188",
        "Lovely spot",
        "There is no lift here at all and we were carried up three flights of stairs.",
        "8.4",
        "July 2025",
    ),
    (
        "91190",
        "Fine week",
        "Breakfast was charged at twelve pounds a head on every morning of our stay.",
        "6.0",
        "June 2025",
    ),
    (
        "91191",
        "Good",
        "Parking was easy and the harbour walk starts right outside the front door.",
        "9.0",
        "May 2025",
    ),
)


def page(reviews: tuple[tuple[str, str, str, str, str], ...], next_page: str = "") -> str:
    """Return a review page in the shape the seaboard channel serves."""
    blocks = "".join(
        f'<article class="review" data-id="{number}">'
        f'<h3 class="title">{title}</h3>'
        f'<p class="body">{body}</p>'
        f'<span class="score" data-value="{score}">{score}</span>'
        f'<span class="stay">{stay}</span>'
        "</article>"
        for number, title, body, score, stay in reviews
    )
    link = f'<a class="next" href="{next_page}">next</a>' if next_page else ""
    return f'<html><body><div id="reviews">{blocks}</div>{link}</body></html>'


@pytest.fixture
def seaboard_profile() -> Profile:
    """The profile that reads the seaboard markup."""
    return Profile(
        channel="seaboard",
        version=1,
        container="article.review",
        fields=(
            FieldRule("channel_review_id", "attribute", "article.review", "data-id", required=True),
            FieldRule("title", "text", "h3.title"),
            FieldRule("body", "text", "p.body", required=True),
            FieldRule("score", "attribute", "span.score", "data-value", required=True),
            FieldRule("stay_month", "text", "span.stay"),
        ),
        next_page="a.next",
    )
