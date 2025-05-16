"""Pages and profiles the parse tests read."""

from __future__ import annotations

import pytest

from tariffpeg.parse.profile import FieldRule, Profile

MARKUP = """
<div id="reviews">
  <article class="review" data-id="91188">
    <h3 class="title">Lovely spot</h3>
    <p class="body">The lift was out all week.</p>
    <span class="score" data-value="8.4">8.4</span>
    <span class="stay">June 2025</span>
  </article>
  <article class="review" data-id="91190">
    <h3 class="title">Bien</h3>
    <p class="body">No breakfast was served.</p>
    <span class="score" data-value="6.0">6.0</span>
    <span class="stay">July 2025</span>
  </article>
</div>
<a class="next" href="/p/1/reviews?page=2">next</a>
"""


@pytest.fixture
def markup() -> str:
    """A two review page in the shape the seaboard channel serves."""
    return MARKUP


@pytest.fixture
def profile() -> Profile:
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
