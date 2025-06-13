"""Every quotation in a case file traces back to the bytes that were served."""

from __future__ import annotations

import datetime as dt

import pytest

from tariffpeg.errors import Invalid
from tariffpeg.model.period import Season, StayMonth
from tariffpeg.model.review import Review

DIGEST = "sha256:" + "a" * 64
BODY = "The lift was out for the whole week and nobody at the desk mentioned it once."


def make(**over: object) -> Review:
    base: dict[str, object] = {
        "channel": "seaboard",
        "channel_review_id": "91188",
        "licence_serial": 4021,
        "stay": StayMonth(2025, 7),
        "unit_points": 74,
        "raw_score": "8.4",
        "body": BODY,
        "capture_digest": DIGEST,
        "profile_key": "seaboard/v1",
    }
    base.update(over)
    return Review(**base)  # type: ignore[arg-type]


def test_the_key_carries_the_channel_because_channels_reuse_numbers() -> None:
    assert make().key == "seaboard:91188"


def test_a_review_belongs_to_a_channel_slug() -> None:
    with pytest.raises(Invalid, match="channel slug"):
        make(channel="Seaboard Stays")


def test_a_review_needs_an_id_from_its_channel() -> None:
    with pytest.raises(Invalid, match="needs an id"):
        make(channel_review_id="   ")


def test_a_score_off_the_unit_scale_is_refused() -> None:
    with pytest.raises(Invalid, match="nought to a hundred"):
        make(unit_points=101)
    with pytest.raises(Invalid, match="nought to a hundred"):
        make(unit_points=-1)


def test_a_review_with_no_words_in_it_is_not_evidence() -> None:
    with pytest.raises(Invalid, match="not evidence"):
        make(body="   ")


def test_a_review_has_to_name_the_capture_it_came_from() -> None:
    with pytest.raises(Invalid, match="names the capture"):
        make(capture_digest="deadbeef")


def test_a_review_has_to_name_the_profile_that_read_it() -> None:
    with pytest.raises(Invalid, match="names the profile"):
        make(profile_key="")


def test_a_body_that_still_carries_personal_data_is_refused() -> None:
    with pytest.raises(Invalid, match="still carries personal data"):
        make(body="Ring the owner on 01736 555 0142 about the lift.")
    with pytest.raises(Invalid, match="still carries personal data"):
        make(body="Write to ada@example.test about the lift being out all week.")


def test_a_room_class_has_to_be_a_slug_when_there_is_one() -> None:
    assert make(room_class="twin-en-suite").room_class == "twin-en-suite"
    assert make().room_class == ""
    with pytest.raises(Invalid, match="room class is a slug"):
        make(room_class="Twin En Suite")


def test_a_negative_licence_serial_is_refused() -> None:
    with pytest.raises(Invalid, match="not negative"):
        make(licence_serial=-1)


def test_the_word_count_is_what_the_guest_wrote() -> None:
    assert make().words() == 16
    assert make(body="Fine.").words() == 1


def test_a_short_review_counts_towards_the_sample_but_carries_no_assertion() -> None:
    assert make().is_substantial()
    assert not make(body="Nice enough, would come back.").is_substantial()


def test_a_review_reports_the_season_its_stay_fell_in() -> None:
    assert make().season() is Season.PEAK
    assert make(stay=StayMonth(2025, 2)).season() is Season.OFF


def test_the_age_of_a_stay_is_counted_in_months() -> None:
    assert make().age_in_months(StayMonth(2026, 1)) == 6
    assert make().age_in_months(StayMonth(2025, 7)) == 0


def test_a_review_knows_whether_the_operator_replied() -> None:
    assert not make().has_response()
    assert make(operator_response="We are sorry, the lift is fixed.").has_response()
    assert not make(operator_response="   ").has_response()


def test_a_short_quotation_comes_back_whole() -> None:
    assert make().quote() == BODY


def test_a_long_quotation_is_cut_on_a_word_and_says_it_was_cut() -> None:
    long_body = " ".join(["the lift was out"] * 40)
    quoted = make(body=long_body).quote(60)
    assert quoted.endswith("[...]")
    assert len(quoted) <= 66
    assert not quoted.replace(" [...]", "").endswith("lif")


def test_a_quotation_collapses_the_whitespace_the_page_had_in_it() -> None:
    assert make(body="The lift\n   was   out.").quote() == "The lift was out."


def test_the_optional_fields_default_to_nothing() -> None:
    review = make()
    assert review.title == ""
    assert review.reviewer_initials == ""
    assert review.language == "en"
    assert review.submitted is None


def test_the_submitted_date_is_kept_when_the_channel_gives_one() -> None:
    assert make(submitted=dt.date(2025, 8, 3)).submitted == dt.date(2025, 8, 3)
