from __future__ import annotations

from dataclasses import dataclass
import importlib

from .config import ROOT, settings
from .policy import policy_from_settings


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    blocking: bool = True


REQUIRED_MODULES = [
    "app.browser",
    "app.linkedin_reader",
    "app.skill_runtime",
    "app.skill_registry",
    "app.content_skills",
    "app.application_tracker",
    "app.history",
    "app.approval_queue",
    "app.orchestrator",
    "app.selector_health",
]


def run_doctor() -> list[Check]:
    checks: list[Check] = []

    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
            checks.append(Check(f"module:{module}", True, "import ok"))
        except Exception as exc:
            checks.append(Check(f"module:{module}", False, str(exc)))

    try:
        settings.profile_path.mkdir(parents=True, exist_ok=True)
        checks.append(Check("browser-profile", True, str(settings.profile_path)))
    except Exception as exc:
        checks.append(Check("browser-profile", False, str(exc)))

    try:
        policy = policy_from_settings()
        checks.append(
            Check(
                "policy",
                True,
                f"dry_run={policy.dry_run}, approval_required={policy.require_human_approval}",
            )
        )
    except Exception as exc:
        checks.append(Check("policy", False, str(exc)))

    checks.append(
        Check(
            "dry-run",
            settings.dry_run,
            f"DRY_RUN={settings.dry_run} (recommended during validation)",
            blocking=False,
        )
    )
    checks.append(
        Check(
            "approval",
            settings.approval_required,
            f"APPROVAL_REQUIRED={settings.approval_required}",
            blocking=True,
        )
    )
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            executable = pw.chromium.executable_path
        browser_ok = bool(executable) and __import__("pathlib").Path(executable).exists()
        checks.append(
            Check(
                "chromium-runtime",
                browser_ok,
                executable if executable else "Chromium executable path unavailable",
            )
        )
    except Exception as exc:
        checks.append(Check("chromium-runtime", False, f"{type(exc).__name__}: {exc}"))

    checks.append(
        Check(
            "linkedin-url",
            settings.linkedin_base_url.startswith("https://www.linkedin.com"),
            settings.linkedin_base_url,
        )
    )
    checks.append(Check("project-root", ROOT.exists(), str(ROOT)))
    return checks
