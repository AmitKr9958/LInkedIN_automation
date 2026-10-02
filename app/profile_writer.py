from __future__ import annotations

import re
from typing import Any

from .browser import linkedin_browser
from .config import settings
from .linkedin_reader import current_session_state
from .skills.profile import read_profile
from .profile_optimizer import profile_fingerprint
from .profile_grounding import validate_profile_drafts


class ProfileWriteError(RuntimeError):
    """Raised when an approved profile proposal cannot be safely applied."""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


async def _click_edit(page, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        try:
            loc = page.locator(f"button[aria-label*='{pattern}' i], button[data-control-name*='{pattern}' i]")
            if await loc.count():
                await loc.first.click()
                return True
        except Exception:
            pass
    try:
        buttons = page.get_by_role("button")
        count = await buttons.count()
        for i in range(min(count, 120)):
            b = buttons.nth(i)
            try:
                label = _clean(await b.get_attribute("aria-label"))
                text = _clean(await b.inner_text())
                if any(re.search(pattern, f"{label} {text}", re.I) for pattern in patterns):
                    await b.click()
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


async def _dialog(page):
    try:
        dialogs = page.get_by_role("dialog")
        if await dialogs.count():
            return dialogs.last
    except Exception:
        pass
    return page.locator("body")


async def _fill_matching_field(dialog, old_value: str, new_value: str, field_kind: str) -> bool:
    old = _clean(old_value)
    candidates = dialog.locator("input, textarea, [contenteditable='true']")
    count = await candidates.count()
    # First prefer a field whose current value exactly matches the approved snapshot.
    for i in range(min(count, 30)):
        loc = candidates.nth(i)
        try:
            current = _clean(await loc.input_value()) if await loc.evaluate("el => 'value' in el") else _clean(await loc.inner_text())
            if old and current == old:
                await loc.fill(new_value)
                return True
        except Exception:
            continue
    # Then use semantic field hints, but only within the active dialog.
    hints = {
        "headline": ("headline",),
        "about": ("about", "summary"),
    }.get(field_kind, (field_kind,))
    for i in range(min(count, 30)):
        loc = candidates.nth(i)
        try:
            blob = " ".join([
                _clean(await loc.get_attribute("name")),
                _clean(await loc.get_attribute("id")),
                _clean(await loc.get_attribute("aria-label")),
                _clean(await loc.get_attribute("placeholder")),
            ])
            if any(hint in blob.lower() for hint in hints):
                await loc.fill(new_value)
                return True
        except Exception:
            continue
    return False


async def _save_dialog(dialog) -> None:
    try:
        save = dialog.get_by_role("button", name=re.compile(r"^save(?: changes)?$", re.I))
        if await save.count():
            await save.last.click()
            return
    except Exception:
        pass
    try:
        buttons = dialog.locator("button")
        for i in range(await buttons.count()):
            b = buttons.nth(i)
            label = _clean(await b.inner_text())
            if re.fullmatch(r"save(?: changes)?", label, re.I):
                await b.click()
                return
    except Exception:
        pass
    raise ProfileWriteError("Could not find the Save button in the active LinkedIn dialog.")


async def _apply_field(page, section: str, old_value: str, new_value: str) -> None:
    if not _clean(new_value):
        return
    patterns = {
        "headline": ("edit intro", "edit headline"),
        "about": ("edit about",),
    }
    if not await _click_edit(page, patterns[section]):
        raise ProfileWriteError(f"Could not locate LinkedIn's Edit control for {section}.")
    await page.wait_for_timeout(600)
    dialog = await _dialog(page)
    if not await _fill_matching_field(dialog, old_value, new_value, section):
        raise ProfileWriteError(f"Could not safely locate the {section} field in the edit dialog.")
    await _save_dialog(dialog)
    await page.wait_for_timeout(1200)


async def apply_approved_profile_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    """Apply only an approved, fingerprint-matched profile proposal.

    This intentionally supports headline/About only. Experience is aggregated
    by the reader and cannot be safely mapped to a single LinkedIn edit form.
    """
    if not settings.linkedin_profile_write_enabled:
        raise ProfileWriteError(
            "Profile writes are disabled. Set LINKEDIN_PROFILE_WRITE_ENABLED=true "
            "explicitly before applying an approved proposal."
        )
    if settings.dry_run:
        raise ProfileWriteError("Profile writes are blocked while DRY_RUN=true.")
    if not settings.profile_url:
        raise ProfileWriteError("PROFILE_URL is required.")

    expected = _clean(proposal.get("profile_fingerprint"))
    if not expected:
        raise ProfileWriteError("Approval proposal has no profile fingerprint; legacy approvals are not executable.")

    drafts = proposal.get("drafts")
    profile = proposal.get("profile")
    if not isinstance(drafts, dict) or not isinstance(profile, dict):
        raise ProfileWriteError("Approval proposal is missing its profile snapshot or drafts.")

    grounding = validate_profile_drafts(profile, drafts)
    if not grounding["publishable"]:
        issues = []
        for item in grounding["blocking_issues"]:
            values = ", ".join(str(value) for value in item.get("values", []))
            issues.append(f'{item["field"]}: {item["type"]}' + (f" ({values})" if values else ""))
        raise ProfileWriteError(
            "Approved proposal failed source-grounding validation; no LinkedIn changes were made. "
            + "; ".join(issues)
        )

    async with linkedin_browser(headless=settings.headless) as context:
        page = context.pages[0] if context.pages else await context.new_page()
        snapshot = await read_profile(page)
        current = snapshot.to_dict()
        if not current.get("authenticated"):
            raise ProfileWriteError("LinkedIn session is not authenticated.")
        actual = profile_fingerprint(current)
        if actual != expected:
            raise ProfileWriteError(
                "The LinkedIn profile changed after approval. The proposal is stale and was not applied."
            )

        old_headline = _clean(profile.get("headline"))
        old_about = _clean(profile.get("about"))
        applied: list[str] = []
        skipped: list[str] = []

        if _clean(drafts.get("headline")) and _clean(drafts.get("headline")) != old_headline:
            await _apply_field(page, "headline", old_headline, _clean(drafts["headline"]))
            applied.append("headline")
        if _clean(drafts.get("about")) and _clean(drafts.get("about")) != old_about:
            await _apply_field(page, "about", old_about, _clean(drafts["about"]))
            applied.append("about")
        if _clean(drafts.get("experience")):
            skipped.append("experience (manual review required)")

        verify = await read_profile(page)
        verified: list[str] = []
        if "headline" in applied and _clean(verify.headline) == _clean(drafts["headline"]):
            verified.append("headline")
        if "about" in applied and _clean(verify.about).lower().find(_clean(drafts["about"]).lower()) >= 0:
            verified.append("about")

        failed = [field for field in applied if field not in verified]
        if failed:
            raise ProfileWriteError(
                "Post-save verification failed for: " + ", ".join(failed) + "."
            )

        return {
            "applied": applied,
            "verified": verified,
            "skipped": skipped,
            "profile_url": current.get("url") or settings.profile_url,
        }
