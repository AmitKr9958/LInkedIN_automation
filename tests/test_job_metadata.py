from app.job_metadata import experience_matches, parse_applicant_count, parse_experience


def test_applicant_count_variants():
    assert parse_applicant_count("25 applicants").count == 25
    assert parse_applicant_count("Over 100 applicants").count == 100
    assert parse_applicant_count("Be among the first 25 applicants").count == 25
    assert parse_applicant_count("no count").count is None


def test_experience_variants():
    assert parse_experience("5-8 years").low == 5
    assert parse_experience("8+ years").low == 8
    assert parse_experience("minimum 5 years").low == 5
    assert parse_experience("Senior Power BI Developer", "Senior Power BI Developer").detected


def test_experience_match_unknown_is_not_rejected():
    info = parse_experience("experience not specified")
    assert info.detected is False
    assert experience_matches(info, 5, 12) is None


def test_experience_overlap():
    assert experience_matches(parse_experience("5-8 years"), 5, 12) is True
    assert experience_matches(parse_experience("0-1 years"), 5, 12) is False
