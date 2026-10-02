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


def test_details_section_guard_rejects_recommendations():
    assert not profile._is_plausible_details_section(
        "Connect Val R. · 3rd Human Resources Manager Connect Paul Maxwell · 2nd Director",
        "experience",
    )


def test_details_section_guard_requires_experience_date_signal():
    assert not profile._is_plausible_details_section(
        "Senior Power BI Developer Bill Gosling Outsourcing Business Intelligence",
        "experience",
    )


def test_details_section_guard_accepts_real_experience_shape():
    assert profile._is_plausible_details_section(
        "Senior Power BI Developer Bill Gosling Outsourcing Mar 2024 – Present Delhi "
        "Power BI DAX SQL automated reporting",
        "experience",
    )


def test_details_section_guard_rejects_skills_activity_noise():
    assert not profile._is_plausible_details_section(
        "Activity 2,177 followers Create post People you may know",
        "skills",
    )


def test_details_sections_fail_closed_before_generic_dom_fallbacks():
    source = inspect.getsource(profile._read_profile_section)
    details_pos = source.index("if section_name in _DETAILS_PATHS:")
    fallback_pos = source.index("# Fallback 1:")
    assert details_pos < fallback_pos
    assert 'return ""' in source[details_pos:fallback_pos]
