from app.health import check

def test_health_imports():
    assert check().ok
