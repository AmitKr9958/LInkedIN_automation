from app.profile_debug import debug_about_editor

def test_debug_about_editor_is_exposed():
    assert callable(debug_about_editor)
