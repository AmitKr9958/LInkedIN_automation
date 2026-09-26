from app.skills.jobs import _build_jobs_search_url, _search_location_value


def test_search_location_value_scopes_supported_cities_to_india():
    assert _search_location_value("Delhi") == "Delhi, India"
    assert _search_location_value("New Delhi") == "Delhi, India"
    assert _search_location_value("Gurgaon") == "Gurgaon, India"
    assert _search_location_value("Gurugram") == "Gurgaon, India"
    assert _search_location_value("Noida") == "Noida, India"
    assert _search_location_value("Jaipur") == "Jaipur, India"


def test_search_location_value_does_not_duplicate_india():
    assert _search_location_value("Delhi, India") == "Delhi, India"
    assert _search_location_value("Gurgaon, Haryana, India") == "Gurgaon, Haryana, India"


def test_build_jobs_search_url_uses_country_scoped_location():
    url = _build_jobs_search_url("Power BI Developer", "Delhi")
    assert "keywords=Power+BI+Developer" in url
    assert "location=Delhi%2C+India" in url


def test_build_jobs_search_url_preserves_start():
    url = _build_jobs_search_url("Power BI Developer", "Gurgaon", 25)
    assert "location=Gurgaon%2C+India" in url
    assert "start=25" in url
