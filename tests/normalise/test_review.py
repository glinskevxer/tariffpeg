"""One bad review on a page must not cost the other thirty nine."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.model.channel import Channel, FetchPolicy, SyndicationClass
from tariffpeg.model.period import StayMonth
from tariffpeg.normalise.review import (
    normalise,
    normalise_language,
    normalise_room_class,
    parse_submitted,
)
from tariffpeg.parse.extract import RawReview

DIGEST = "sha256:" + "b" * 64
AGENT = "tariffpeg-harvester (standards@example-authority.test)"
BODY = "The lift was out for the whole week and nobody at the desk mentioned it."


@pytest.fixture
def channel() -> Channel:
    return Channel(
        slug="seaboard",
        name="Seaboard Stays",
        base_url="https://seaboard.example",
        syndication=SyndicationClass.PRIMARY,
        policy=FetchPolicy(AGENT, 1500, 400),
        scale_slug="ten-point",
    )


def raw(**over: str) -> RawReview:
    fields = {
        "channel_review_id": "91188",
        "body": BODY,
        "score": "8.4",
        "stay_month": "July 2025",
    }
    fields.update(over)
    return RawReview(fields, "seaboard/v1", 0)


def test_a_clean_review_normalises_with_nothing_to_report(channel: Channel) -> None:
    found = normalise(raw(), channel, 4021, DIGEST)
    assert found.ok
    assert found.problems == ()
    assert found.review is not None
    assert found.review.unit_points == 79
    assert found.review.raw_score == "8.4"
    assert found.review.stay == StayMonth(2025, 7)


def test_the_score_is_put_on_the_unit_scale_through_the_channel_dial(channel: Channel) -> None:
    found = normalise(raw(score="8"), channel, 4021, DIGEST)
    assert found.review is not None
    assert found.review.unit_points == 74


def test_a_score_off_the_dial_loses_that_review_and_nothing_else(channel: Channel) -> None:
    found = normalise(raw(score="11"), channel, 4021, DIGEST)
    assert not found.ok
    assert found.problems == ("seaboard block 0: this dial runs from 10 to a hundred",)


def test_a_score_that_is_not_a_number_loses_that_review(channel: Channel) -> None:
    found = normalise(raw(score="great"), channel, 4021, DIGEST)
    assert not found.ok
    assert "is a number" in found.problems[0]


def test_a_stay_month_in_any_known_shape_is_read(channel: Channel) -> None:
    for written in ("July 2025", "2025-07", "07/2025"):
        found = normalise(raw(stay_month=written), channel, 4021, DIGEST)
        assert found.review is not None
        assert found.review.stay == StayMonth(2025, 7)


def test_a_stay_month_the_reader_does_not_know_falls_back_to_the_submission_date(
    channel: Channel,
) -> None:
    found = normalise(raw(stay_month="last summer", submitted="2025-08-03"), channel, 4021, DIGEST)
    assert found.review is not None
    assert found.review.stay == StayMonth(2025, 8)
    assert any("not a shape" in problem for problem in found.problems)
    assert any("taken from the submission date" in problem for problem in found.problems)


def test_a_review_with_no_month_at_all_is_lost_and_says_why(channel: Channel) -> None:
    found = normalise(raw(stay_month=""), channel, 4021, DIGEST)
    assert not found.ok
    assert "no stay month and no submission date" in found.problems[0]


def test_the_body_is_redacted_and_the_removal_is_reported(channel: Channel) -> None:
    dirty = "Ring the owner on 01736 555 0142, the lift was out all week."
    found = normalise(raw(body=dirty), channel, 4021, DIGEST)
    assert found.review is not None
    assert "01736" not in found.review.body
    assert any("telephone removed" in problem for problem in found.problems)


def test_the_reviewer_name_is_reduced_to_initials_and_taken_out_of_the_body(
    channel: Channel,
) -> None:
    found = normalise(
        raw(body="Ada thought the lift being out all week was poor.", reviewer="Ada Lovelace"),
        channel,
        4021,
        DIGEST,
    )
    assert found.review is not None
    assert found.review.reviewer_initials == "A. L."
    assert "Ada" not in found.review.body


def test_the_title_and_the_response_are_redacted_too(channel: Channel) -> None:
    found = normalise(
        raw(title="Ada was here", response="Write to us at owner@example.test", reviewer="Ada"),
        channel,
        4021,
        DIGEST,
    )
    assert found.review is not None
    assert "Ada" not in found.review.title
    assert "example.test" not in found.review.operator_response


def test_a_room_class_becomes_a_slug(channel: Channel) -> None:
    found = normalise(raw(room_class="Twin En Suite"), channel, 4021, DIGEST)
    assert found.review is not None
    assert found.review.room_class == "twin-en-suite"


def test_a_room_class_that_will_not_become_a_slug_is_dropped(channel: Channel) -> None:
    assert normalise_room_class("2 star") == ""
    assert normalise_room_class("   ") == ""
    assert normalise_room_class("Sea View") == "sea-view"


def test_the_language_tag_is_reduced_to_its_first_subtag(channel: Channel) -> None:
    found = normalise(raw(language="en-GB"), channel, 4021, DIGEST)
    assert found.review is not None
    assert found.review.language == "en"


def test_a_review_with_no_language_falls_back_to_the_channel_locale(channel: Channel) -> None:
    found = normalise(raw(), channel, 4021, DIGEST)
    assert found.review is not None
    assert found.review.language == "en"
    assert normalise_language("", "fr") == "fr"
    assert normalise_language("!!", "fr") == "fr"


def test_a_submission_date_is_read_in_the_shapes_channels_print_it() -> None:
    assert parse_submitted("2025-08-03") == dt.date(2025, 8, 3)
    assert parse_submitted("03/08/2025") == dt.date(2025, 8, 3)
    assert parse_submitted("3 August 2025") == dt.date(2025, 8, 3)
    assert parse_submitted("3 Aug 2025") == dt.date(2025, 8, 3)
    assert parse_submitted("August 3, 2025") == dt.date(2025, 8, 3)


def test_a_submission_date_in_no_known_shape_is_simply_absent() -> None:
    assert parse_submitted("some time last year") is None
    assert parse_submitted("   ") is None


def test_a_review_the_store_would_refuse_is_lost_with_the_reason(channel: Channel) -> None:
    found = normalise(raw(body="   "), channel, 4021, DIGEST)
    assert not found.ok
    assert any("not evidence" in problem for problem in found.problems)


def test_the_profile_and_the_capture_are_carried_onto_the_review(channel: Channel) -> None:
    found = normalise(raw(), channel, 4021, DIGEST)
    assert found.review is not None
    assert found.review.profile_key == "seaboard/v1"
    assert found.review.capture_digest == DIGEST
    assert found.review.licence_serial == 4021


def test_a_normalised_result_with_nothing_in_it_carries_no_review() -> None:
    from tariffpeg.normalise.review import Normalised

    assert not Normalised().ok
    assert Normalised(problems=("x",)).problems == ("x",)
