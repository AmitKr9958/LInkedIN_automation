import inspect

from app.skills import profile


def test_section_details_are_preferred_before_generic_dom_extraction():
    source = inspect.getsource(profile._read_profile_section)
    details_pos = source.index("if section_name in _DETAILS_PATHS:")
    generic_dom_pos = source.index("# Fallback 1:")
    assert details_pos < generic_dom_pos


def test_experience_details_route_is_section_scoped():
    source = inspect.getsource(profile._read_profile_details_page)
    assert '_details_url_matches(str(detail_page.url or ""), slug, section_name)' in source
    assert 'detail_page.locator("main").first.inner_text()' in source
