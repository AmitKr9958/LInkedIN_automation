from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scheduler_runner_is_hidden_and_non_interactive():
    """Hidden path is wscript -> VBS -> PowerShell -WindowStyle Hidden -NonInteractive."""
    installer = (ROOT / "scripts" / "install-readonly-scheduler.ps1").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts" / "run-agent-hidden.vbs").read_text(encoding="utf-8")
    assert "wscript.exe" in installer.lower()
    assert "-Hidden" in installer
    assert "-NonInteractive" in launcher
    assert "-NoLogo" in launcher
    assert "-WindowStyle Hidden" in launcher


def test_scheduler_is_hidden_and_single_instance():
    text = (ROOT / "scripts" / "install-readonly-scheduler.ps1").read_text(encoding="utf-8")
    assert " -Hidden" in text
    assert "-MultipleInstances IgnoreNew" in text
    assert "-RepetitionInterval (New-TimeSpan -Hours 2)" in text


def test_scheduler_uses_30_minute_agent_window():
    text = (ROOT / "scripts" / "run-agent.ps1").read_text(encoding="utf-8")
    assert "--max-posted-hours 0.5" in text
    assert "--max-posted-hours 48" not in text


def test_scheduler_uses_wscript_hidden_launcher():
    root = Path(__file__).resolve().parents[1]
    installer = (root / "scripts" / "install-readonly-scheduler.ps1").read_text(encoding="utf-8")
    launcher = (root / "scripts" / "run-agent-hidden.vbs").read_text(encoding="utf-8")
    assert "wscript.exe" in installer.lower()
    assert "run-agent-hidden.vbs" in installer
    assert "shell.Run(cmd, 0, True)" in launcher
    assert "-WindowStyle Hidden" in launcher


def test_scheduler_timeout_exceeds_20_minutes():
    """Timeout must exceed measured worst-case cycle; 20m was killing healthy runs."""
    text = (ROOT / "scripts" / "install-readonly-scheduler.ps1").read_text(encoding="utf-8")
    assert "Minutes 20" not in text
    assert "Minutes 45" in text or "Minutes 40" in text or "Minutes 50" in text


def test_scheduler_status_exposes_diagnostics():
    text = (ROOT / "scripts" / "scheduler-status.ps1").read_text(encoding="utf-8")
    assert "ExecutionTimeLimit" in text
    assert "MultipleInstances" in text
    assert "StartWhenAvailable" in text
    assert "Execute:" in text

def test_scheduler_explicitly_enables_agent_gate():
    text = (ROOT / "scripts" / "run-agent.ps1").read_text(encoding="utf-8")
    assert '$env:LINKEDIN_AGENT_ENABLED = "true"' in text


def test_agent_gate_defaults_closed():
    text = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    assert "agent_enabled: bool = False" in text

def test_job_detail_hydration_is_conservative():
    text = (ROOT / "app" / "skills" / "jobs.py").read_text(encoding="utf-8")
    assert "MAX_DETAIL_HYDRATION = 8" in text
    assert "MAX_DETAIL_HYDRATION = 25" not in text


def test_people_search_is_disabled_in_daily_agent():
    text = (ROOT / "app" / "daily_agent.py").read_text(encoding="utf-8")
    assert 'diagnostics["people_search_enabled"] = False' in text
    assert 'query="recruiter Power BI Data Analyst"' not in text
