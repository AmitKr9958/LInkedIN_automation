from app.skills.profile import _is_valid_headline, _parse_top_card


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
