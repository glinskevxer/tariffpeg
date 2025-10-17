"""The unit has no business keeping the name, only what was said about the lift."""

from __future__ import annotations

from tariffpeg.model.redaction import Redacted, is_clean, redact, redact_name


def test_a_review_with_nothing_personal_in_it_comes_back_unchanged() -> None:
    body = "The lift was out all week and nobody said anything about it."
    found = redact(body)
    assert found.text == body
    assert not found.changed
    assert found.summary() == "nothing removed"


def test_an_email_address_is_taken_out() -> None:
    found = redact("Write to ada.lovelace+stay@example.test if you want the details.")
    assert "example.test" not in found.text
    assert "[email removed]" in found.text
    assert found.count("email") == 1


def test_a_link_is_taken_out_before_the_address_inside_it_is_read() -> None:
    found = redact("See https://example.test/u/ada@example.test for photographs.")
    assert found.count("link") == 1
    assert found.count("email") == 0
    assert "[link removed]" in found.text


def test_a_bare_www_link_is_taken_out_too() -> None:
    assert redact("Look at www.example.test/rooms").count("link") == 1


def test_a_telephone_number_is_taken_out() -> None:
    for written in ("01736 555 0142", "+44 1736 5550142", "(01736) 555-0142"):
        found = redact(f"The owner said to ring {written} on arrival.")
        assert found.count("telephone") == 1, written
        assert "[telephone removed]" in found.text


def test_a_short_run_of_digits_is_not_a_telephone_number() -> None:
    found = redact("Room 12 was noisy and the score was 8.4 out of 10.")
    assert found.count("telephone") == 0
    assert "8.4" in found.text


def test_a_year_is_not_a_telephone_number() -> None:
    assert redact("We stayed in 2025 and again in 2026.").count("telephone") == 0


def test_a_booking_reference_is_taken_out() -> None:
    found = redact("My booking was AB12CD34 and nobody could find it.")
    assert found.count("reference") == 1
    assert "AB12CD34" not in found.text


def test_a_plain_word_in_capitals_is_not_a_booking_reference() -> None:
    found = redact("The room was AWFUL and the shower was COLD.")
    assert found.count("reference") == 0
    assert "AWFUL" in found.text


def test_the_reviewer_name_is_taken_out_wherever_it_appears() -> None:
    found = redact("Ada said the lift was out. Ada was right.", "Ada")
    assert found.count("name") == 2
    assert "Ada" not in found.text


def test_the_reviewer_name_is_matched_without_minding_case() -> None:
    assert redact("ADA said so.", "Ada").count("name") == 1


def test_a_blank_reviewer_name_takes_nothing_out() -> None:
    body = "The lift was out."
    assert redact(body, "   ").text == body


def test_a_name_with_a_regular_expression_in_it_is_matched_literally() -> None:
    found = redact("A guest called A.B. wrote this.", "A.B.")
    assert found.count("name") == 1


def test_several_kinds_are_reported_in_a_fixed_order() -> None:
    found = redact(
        "Ring 01736 555 0142 or write to ada@example.test, booking AB12CD34, from Ada.",
        "Ada",
    )
    assert [kind for kind, _ in found.removed] == ["email", "telephone", "reference", "name"]
    assert "removed" in found.summary()


def test_the_summary_counts_each_kind() -> None:
    found = redact("ada@example.test and bea@example.test")
    assert found.summary() == "2 email removed"


def test_a_display_name_is_reduced_to_initials() -> None:
    assert redact_name("Ada Lovelace") == "A. L."
    assert redact_name("ada") == "A."
    assert redact_name("Ada B. Lovelace") == "A. B. L."


def test_a_name_that_is_already_initials_stays_that_way() -> None:
    assert redact_name("A. L.") == "A. L."


def test_a_blank_display_name_reduces_to_nothing() -> None:
    assert redact_name("   ") == ""


def test_text_that_has_been_through_the_redactor_reads_as_clean() -> None:
    dirty = "Ring 01736 555 0142 or write to ada@example.test about booking AB12CD34."
    assert not is_clean(dirty)
    assert is_clean(redact(dirty).text)


def test_a_body_with_a_link_still_in_it_does_not_read_as_clean() -> None:
    assert not is_clean("See https://example.test/rooms")


def test_a_redacted_value_reports_a_kind_it_never_saw_as_nothing() -> None:
    assert Redacted("text").count("email") == 0
