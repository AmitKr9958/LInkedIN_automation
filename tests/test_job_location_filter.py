from app.skills.jobs import _location_matches_requested, _normalize_location_text


def test_gurgaon_matches_gurugram():
    assert _location_matches_requested("Gurugram, Haryana, India (On-site)", "Gurgaon")


def test_gurugram_request_matches_gurgaon_card():
    assert _location_matches_requested("Gurgaon, Haryana, India", "Gurugram")


def test_delhi_matches_new_delhi():
    assert _location_matches_requested("New Delhi, Delhi, India", "Delhi")


def test_new_delhi_request_matches_delhi_card():
    assert _location_matches_requested("Delhi, India", "New Delhi")


def test_case_and_whitespace_insensitive():
    assert _location_matches_requested("  GURGAON , Haryana ", "gurgaon")


def test_noida_does_not_match_gurgaon():
    assert not _location_matches_requested("Noida, Uttar Pradesh, India (On-site)", "Gurgaon")


def test_jaipur_does_not_match_delhi():
    assert not _location_matches_requested("Jaipur, Rajasthan, India", "Delhi")


def test_india_remote_does_not_match_city():
    assert not _location_matches_requested("India (Remote)", "Gurgaon")


def test_us_remote_does_not_match_delhi():
    assert not _location_matches_requested("United States (Remote)", "Delhi")


def test_city_remote_matches_when_city_is_explicit():
    assert _location_matches_requested("Gurgaon, Haryana, India (Remote)", "Gurgaon")


def test_empty_location_does_not_match_requested_city():
    assert not _location_matches_requested("", "Gurgaon")


def test_normalize_aliases():
    assert "gurgaon" in _normalize_location_text("Gurugram, Haryana").split()
    assert "delhi" in _normalize_location_text("New Delhi, India").split()
