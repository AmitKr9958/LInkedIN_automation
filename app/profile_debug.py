"""Read-only diagnostics for LinkedIn's live About editor UI."""
from __future__ import annotations

from typing import Any


async def _prepare_profile(page) -> None:
    """Load lazy profile content before inspecting the live DOM."""
    try:
        from .linkedin_reader import _scroll_profile_to_bottom, _expand_profile_sections

        await _scroll_profile_to_bottom(page, max_rounds=30)
        await _expand_profile_sections(page)
        # Give lazy-rendered cards a little time to mount, then return to the
        # About area near the top without changing any profile data.
        await page.wait_for_timeout(1000)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(750)
    except Exception:
        # Diagnostics should still return useful evidence if a helper changes.
        try:
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass


async def debug_about_editor(page) -> dict[str, Any]:
    result = {
        "url": page.url,
        "title": await page.title(),
        "authenticated": False,
        "about_headings": [],
        "about_text_matches": [],
        "edit_candidates": [],
        "selected_candidate": None,
        "dialog": {"opened": False, "role": None, "text": "", "fields": []},
        "actions": [],
        "errors": [],
    }

    try:
        from .linkedin_reader import current_session_state

        state = await current_session_state(page)
        result["authenticated"] = bool(state.get("authenticated"))
        result["session"] = state
    except Exception as exc:
        result["errors"].append(f"session:{type(exc).__name__}:{exc}")

    await _prepare_profile(page)
    result["actions"].append("profile_scrolled_and_lazy_content_prepared")

    try:
        headings = page.locator(
            "main h1, main h2, main h3, main h4, main [role='heading'], "
            "main [aria-level]"
        )
        result["about_headings"] = await headings.evaluate_all(
            r"""els => els.map((el, i) => ({
                index: i,
                tag: el.tagName,
                text: (el.innerText || el.textContent || '')
                    .replace(/\s+/g, ' ').trim().slice(0, 300)
            })).filter(x => /\babout\b/i.test(x.text)).slice(0, 20)"""
        )
    except Exception as exc:
        result["errors"].append(f"headings:{type(exc).__name__}:{exc}")

    try:
        result["about_text_matches"] = await page.locator("main *").evaluate_all(
            r"""els => els.map((el, i) => {
                const text = (el.innerText || el.textContent || '')
                    .replace(/\s+/g, ' ').trim();
                return {
                    index: i,
                    tag: el.tagName,
                    text: text.slice(0, 500)
                };
            }).filter(x => /\babout\b/i.test(x.text) && x.text.length < 12000)
              .slice(0, 30)"""
        )
    except Exception as exc:
        result["errors"].append(f"about_text:{type(exc).__name__}:{exc}")

    try:
        controls = page.locator(
            "main button, main a, main [role='button'], main [data-control-name]"
        )
        result["edit_candidates"] = await controls.evaluate_all(
            r"""els => els.map((el, i) => {
                const n = value => (value || '').replace(/\s+/g, ' ').trim();
                const label = n(el.getAttribute('aria-label'));
                const title = n(el.getAttribute('title'));
                const text = n(el.innerText || el.textContent);
                const hay = [label, title, text].join(' ');
                if (!/\bedit\b/i.test(hay)) return null;
                let node = el;
                let aboutScope = false;
                let scopeText = '';
                for (let d = 0; d < 12 && node; d += 1, node = node.parentElement) {
                    const scope = n(node.innerText || node.textContent);
                    if (/\babout\b/i.test(scope) && scope.length < 12000) {
                        aboutScope = true;
                        scopeText = scope.slice(0, 700);
                        break;
                    }
                }
                return {
                    index: i,
                    tag: el.tagName,
                    label,
                    title,
                    text: text.slice(0, 250),
                    aboutScope,
                    scopeText
                };
            }).filter(Boolean).slice(0, 80)"""
        )
    except Exception as exc:
        result["errors"].append(f"candidates:{type(exc).__name__}:{exc}")

    selected = next(
        (x for x in result["edit_candidates"] if x.get("aboutScope")),
        None,
    )
    result["selected_candidate"] = selected

    if selected is None:
        result["actions"].append("no_about_scoped_edit_control_found")
        return result

    try:
        loc = page.locator(
            "main button, main a, main [role='button'], main [data-control-name]"
        ).nth(int(selected["index"]))
        await loc.scroll_into_view_if_needed(timeout=5000)
        await loc.click(timeout=5000)
        result["actions"].append("clicked_about_scoped_edit_control")
    except Exception as exc:
        result["errors"].append(f"click:{type(exc).__name__}:{exc}")
        return result

    try:
        for _ in range(10):
            await page.wait_for_timeout(300)
            dialogs = page.locator("[role='dialog']")
            if await dialogs.count():
                dialog = dialogs.last
                if await dialog.is_visible():
                    fields = await dialog.locator(
                        "textarea,input,[contenteditable='true']"
                    ).evaluate_all(
                        r"""els => els.map((el, i) => ({
                            index: i,
                            tag: el.tagName,
                            name: el.getAttribute('name') || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            placeholder: el.getAttribute('placeholder') || '',
                            role: el.getAttribute('role') || '',
                            valueLength: typeof el.value === 'string'
                                ? el.value.length
                                : (el.innerText || el.textContent || '').length
                        }))"""
                    )
                    result["dialog"] = {
                        "opened": True,
                        "role": await dialog.get_attribute("role"),
                        "text": " ".join((await dialog.inner_text()).split())[:4000],
                        "fields": fields[:20],
                    }
                    break

            modals = page.locator("div[aria-modal='true'], [data-test-modal]")
            if await modals.count():
                modal = modals.last
                if await modal.is_visible():
                    result["dialog"] = {
                        "opened": True,
                        "role": await modal.get_attribute("role"),
                        "text": " ".join((await modal.inner_text()).split())[:4000],
                        "fields": await modal.locator(
                            "textarea,input,[contenteditable='true']"
                        ).evaluate_all(
                            r"""els => els.map((el, i) => ({
                                index: i,
                                tag: el.tagName,
                                name: el.getAttribute('name') || '',
                                ariaLabel: el.getAttribute('aria-label') || '',
                                placeholder: el.getAttribute('placeholder') || '',
                                role: el.getAttribute('role') || '',
                                valueLength: typeof el.value === 'string'
                                    ? el.value.length
                                    : (el.innerText || el.textContent || '').length
                            }))"""
                        ),
                    }
                    break
    except Exception as exc:
        result["errors"].append(f"dialog:{type(exc).__name__}:{exc}")
    finally:
        try:
            await page.keyboard.press("Escape")
            result["actions"].append("closed_with_escape_without_saving")
        except Exception as exc:
            result["errors"].append(f"close:{type(exc).__name__}:{exc}")

    return result
