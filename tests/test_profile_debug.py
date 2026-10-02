from app.profile_debug import debug_about_editor

def test_debug_about_editor_is_exposed():
    assert callable(debug_about_editor)


def test_about_diagnostic_uses_safe_profile_preparation():
    import inspect
    from app import profile_debug

    source = inspect.getsource(profile_debug._prepare_profile)
    assert "from .skills.profile import _expand_profile_sections, _scroll_profile_to_bottom" in source
    assert "prepare:navigation_guard_failed" in source


def test_about_diagnostic_filters_full_text_before_truncation():
    import inspect
    from app import profile_debug

    source = inspect.getsource(profile_debug.debug_about_editor)
    assert "text.length >= 12000" in source
    assert ".filter(Boolean).slice(0, 30)" in source


def test_profile_expanders_do_not_follow_links():
    import inspect
    from app.skills import profile

    source = inspect.getsource(profile._expand_profile_sections)
    assert 'main button, main [role="button"]' in source
    assert "main button, main a, main [role=\"button\"]" not in source

# CI verification: merged About diagnostic fix.
