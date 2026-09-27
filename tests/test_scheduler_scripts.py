from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scheduler_runner_is_hidden_and_non_interactive():
    text = (ROOT / "scripts" / "install-readonly-scheduler.ps1").read_text(encoding="utf-8")
    assert "-WindowStyle Hidden" in text
    assert "-NonInteractive" in text
    assert "-NoLogo" in text


def test_scheduler_is_hidden_and_single_instance():
    text = (ROOT / "scripts" / "install-readonly-scheduler.ps1").read_text(encoding="utf-8")
    assert " -Hidden" in text
    assert "-MultipleInstances IgnoreNew" in text


def test_scheduler_uses_48_hour_agent_window():
    text = (ROOT / "scripts" / "run-agent.ps1").read_text(encoding="utf-8")
    assert "--max-posted-hours 48" in text
    assert "--max-posted-hours 1" not in text
