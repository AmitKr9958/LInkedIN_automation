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


def test_profile_text_normalization_repairs_flattened_inline_nodes():
    raw = "75% queryperformance improvement refreshTechnical stack speedby 2. metrics,enabling 2 mosHandled"
    cleaned = profile._normalize_linkedin_extracted_text(raw)
    assert "query performance" in cleaned
    assert "refresh Technical" in cleaned
    assert "speed by" in cleaned
    assert "metrics, enabling" in cleaned
    assert "2 mos Handled" in cleaned


def test_about_footer_is_removed_and_featured_placeholder_is_empty():
    about = profile._clean_profile_section_text(
        "Real About content … more Top skills Microsoft Power BI • DAX",
        "about",
    )
    assert about == "Real About content"
    featured = profile._clean_profile_section_text(
        "Show what you’re proud of Feature your best articles, posts, documents",
        "featured",
    )
    assert featured == ""


def test_profile_normalization_preserves_canonical_technology_names():
    raw = "Verti Paq My SQL Chat GPT PeopleManagement Power BI Power Query"
    cleaned = profile._normalize_linkedin_extracted_text(raw)
    assert "VertiPaq" in cleaned
    assert "MySQL" in cleaned
    assert "ChatGPT" in cleaned
    assert "People Management" in cleaned
    assert "Power BI" in cleaned
    assert "Power Query" in cleaned


def test_profile_normalization_repairs_concatenated_terms_after_regex_fix():
    cleaned = profile._normalize_linkedin_extracted_text(
        "queryperformance refreshTechnical speedby metrics,enabling 2 mosHandled"
    )
    assert cleaned == "query performance refresh Technical speed by metrics, enabling 2 mos Handled"


def test_profile_normalization_repairs_known_flattened_linkedin_terms():
    raw = (
        "queryperformance refreshTechnical speedby metrics,enabling 2 mosHandled "
        "PowerBI PowerQuery PowerAutomate PowerApps MicrosoftFabric "
        "DataAnalytics BusinessIntelligence AnalystR1 RCM"
    )
    cleaned = profile._normalize_linkedin_extracted_text(raw)
    assert "query performance" in cleaned
    assert "refresh Technical" in cleaned
    assert "speed by" in cleaned
    assert "metrics, enabling" in cleaned
    assert "2 mos Handled" in cleaned
    assert "Power BI" in cleaned
    assert "Power Query" in cleaned
    assert "Power Automate" in cleaned
    assert "Power Apps" in cleaned
    assert "Microsoft Fabric" in cleaned
    assert "Data Analytics" in cleaned
    assert "Business Intelligence" in cleaned
    assert "Analyst R1 RCM" in cleaned


def test_details_noise_removes_profile_language_footer():
    cleaned = profile._clean_details_text(
        "Experience Senior Power BI Developer Mar 2024 - Present Power BI DAX "
        "Profile language English"
    )
    assert "Profile language" not in cleaned
    assert "Senior Power BI Developer" in cleaned
