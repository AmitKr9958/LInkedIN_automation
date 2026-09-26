from app.skills.jobs import _clean_location_candidate, _location_matches_requested, _normalize_location_text, MAX_DETAIL_HYDRATION


def test_gurgaon_matches_gurugram():
    assert _location_matches_requested("Gurugram, Haryana, India (On-site)", "Gurgaon")


def test_gurugram_request_matches_gurgaon_card():
    assert _location_matches_requested("Gurgaon, Haryana, India", "Gurugram")


def test_delhi_matches_new_delhi():
    assert _location_matches_requested("New Delhi, Delhi, India", "Delhi")


def test_new_delhi_request_matches_delhi_card():
    assert _location_matches_requested("Delhi, India", "New Delhi")


def test_case_and_whitespace_insensitive():
    assert _location_matches_requested("  GURGAON , Haryana, India ", "gurgaon")


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


def test_location_candidate_extracts_city_from_metadata_sentence():
    raw = "BI &Analytics Engineer BI &Analytics Engineer Narwal India (Remote) 4 school alumni work here"
    assert _clean_location_candidate(raw) == "India (Remote)"


def test_location_candidate_extracts_delhi_from_metadata_sentence():
    raw = "BI &Analytics Engineer Narwal New Delhi, Delhi, India (On-site) 4 school alumni work here"
    assert _clean_location_candidate(raw) == "New Delhi, Delhi, India (On-site)"


def test_location_candidate_rejects_unbounded_metadata():
    raw = "Delhi University school alumni work here Viewed Easy Apply"
    assert _clean_location_candidate(raw) == ""


def test_detail_hydration_capacity_covers_loaded_search_page():
    assert MAX_DETAIL_HYDRATION >= 25
