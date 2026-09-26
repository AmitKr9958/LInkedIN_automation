import pytest

from app.skills.jobs import _location_from_detail_text


def test_location_from_detail_text_supports_plain_detail_body():
    body = (
        "Power BI Developer Gurugram, Haryana, India "
        "\u00b7 2 hours ago \u00b7 Over 100 applicants"
    )
    assert _location_from_detail_text(body, "Power BI Developer") == "Gurugram, Haryana, India"
