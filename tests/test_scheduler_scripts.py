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


def test_scheduler_installer_is_disabled_by_default():
    text = (ROOT / "scripts" / "install-readonly-scheduler.ps1").read_text(encoding="utf-8")
    assert "[switch]$Enable" in text
    assert "Disable-ScheduledTask -TaskName $TaskName" in text
    assert "if ($Enable)" in text


def test_scheduler_uses_48_hour_agent_window():
    text = (ROOT / "scripts" / "run-agent.ps1").read_text(encoding="utf-8")
    assert "--max-posted-hours" in text
    assert '"48"' in text
    assert "--max-posted-hours 0.5" not in text
    assert "--max-posted-hours 1" not in text


def test_scheduler_runner_sets_start_and_uses_direct_output_redirection():
    text = (ROOT / "scripts" / "run-agent.ps1").read_text(encoding="utf-8")
    assert "$Start = Get-Date" in text
    assert '$env:PYTHONUNBUFFERED = "1"' in text
    assert '$env:PYTHONIOENCODING = "utf-8"' in text
    assert "Start-Process" in text
    assert "-RedirectStandardOutput $StdoutFile" in text
    assert "-RedirectStandardError $StderrFile" in text
    assert "Add-Content -Path $LogFile" in text
