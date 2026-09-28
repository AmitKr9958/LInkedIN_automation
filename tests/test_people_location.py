from app.skills.people import _location_matches


def test_people_location_aliases_accept_gurgaon_variants():
    assert _location_matches("Gurgaon, Haryana, India", "Gurgaon")
    assert _location_matches("Gurugram, India", "Gurgaon/Gurugram")
    assert _location_matches("Gurgaon", "gurugram")


def test_people_location_aliases_support_india():
    assert _location_matches("Bengaluru, Karnataka, India", "India")
    assert not _location_matches("London, England", "India")
