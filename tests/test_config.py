from app.config import settings

def test_safe_defaults():
    assert settings.dry_run is True
    assert settings.approval_required is True


def test_profile_url_default_is_concrete():
    assert settings.profile_url.startswith("https://www.linkedin.com/in/")
    assert settings.profile_url.rstrip("/").split("/in/", 1)[1]
