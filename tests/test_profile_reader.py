from app.skills.profile import (
    _is_valid_headline,
    _normalize_section_heading,
    _parse_top_card,
    _section_heading_matches,
)


def test_pronouns_are_not_headline():
    assert not _is_valid_headline("He/Him")
    assert not _is_valid_headline("She/Her")
    assert not _is_valid_headline("They/Them")


def test_real_headline_is_valid():
    assert _is_valid_headline(
        "Power BI Developer | Business Intelligence | SQL"
    )


def test_top_card_skips_pronouns():
    name, headline, location = _parse_top_card(
        """
        Amit Kumar
        He/Him
        Power BI Developer | Business Intelligence | SQL
        Greater Delhi Area
        """,
        "Amit Kumar",
    )
    assert name == "Amit Kumar"
    assert headline == "Power BI Developer | Business Intelligence | SQL"
    assert location == "Greater Delhi Area"


from app.skills.profile import _normalize_section_heading, _section_heading_matches


def test_section_heading_matching_tolerates_counts_and_whitespace():
    assert _normalize_section_heading("  Experience\u00a0") == "experience"
    assert _section_heading_matches("Experience", "experience")
    assert _section_heading_matches("Skills (25)", "skills")
    assert _section_heading_matches("Featured", "featured")


def test_section_heading_matching_rejects_unrelated_sections():
    assert not _section_heading_matches("Education", "experience")
    assert not _section_heading_matches("Professional Experience", "experience")
