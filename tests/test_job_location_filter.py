from app.skills.jobs import _location_matches_requested


def test_gurgaon_matches_gurugram():
    assert _location_matches_requested("Gurugram, Haryana, India (On-site)", "Gurgaon")


def test_delhi_matches_new_delhi():
    assert _location_matches_requested("New Delhi, Delhi, India", "Delhi")


def test_noida_does_not_match_gurgaon():
    assert not _location_matches_requested("Noida, Uttar Pradesh, India (On-site)", "Gurgaon")


def test_india_remote_does_not_match_city():
    assert not _location_matches_requested("India (Remote)", "Gurgaon")


def test_us_remote_does_not_match_delhi():
    assert not _location_matches_requested("United States (Remote)", "Delhi")


def test_city_remote_matches_when_city_is_explicit():
    assert _location_matches_requested("Gurgaon, Haryana, India (Remote)", "Gurgaon")
