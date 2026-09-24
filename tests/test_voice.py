from app.voice import audit_voice, apply_light_cleanup


def test_voice_metrics_and_cleanup():
    report = audit_voice("We improved refresh time by 20%.")
    assert report["specificity_hint"] is True
    assert report["metrics"]["words"] > 0
    assert apply_light_cleanup("A\n\n\nB") == "A\n\nB"
