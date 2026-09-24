from app.config import settings

def test_safe_defaults():
    assert settings.dry_run is True
    assert settings.approval_required is True
