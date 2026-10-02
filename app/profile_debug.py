"""Read-only diagnostics for LinkedIn's live About editor UI."""
from __future__ import annotations

from typing import Any


async def _prepare_profile(page) -> str:
    """Load lazy profile content while keeping diagnostics on the configured profile."""
    try:
        from .skills.profile import _expand_profile_sections, _scroll_profile_to_bottom
        from .config import settings

        expected_url = str(settings.profile_url or "").strip()
        await _scroll_profile_to_bottom(page, max_rounds=30)
        await _expand_profile_sections(page)
        await page.wait_for_timeout(1000)

        if expected_url and page.url.rstrip("/") != expected_url.rstrip("/"):
            await page.goto(expected_url, wait_until="domcontentloaded", timeout=45_000)
            await page.wait_for_timeout(1500)
            await _scroll_profile_to_bottom(page, max_rounds=12)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(750)
            return "" if page.url.rstrip("/") == expected_url.rstrip("/") else (
                f"prepare:navigation_guard_failed:{page.url}"
            )

        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(750)
        return ""
    except Exception as exc:
        try:
            await page.evaluate("window.scrollTo(0, 0)")
        except Exception:
            pass
        return f"prepare:{type(exc).__name__}:{exc}"

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

    prepare_error = await _prepare_profile(page)
    if prepare_error:
        result["errors"].append(prepare_error)
    else:
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
                if (!/\babout\b/i.test(text) || text.length >= 12000) return null;
                return {index: i, tag: el.tagName, text: text.slice(0, 500)};
            }).filter(Boolean).slice(0, 30)"""
        )
    except Exception as exc:
        result["errors"].append(f"about_text:{type(exc).__name__}:{exc}")

    try:
        controls = page.locator(
            "main button, main a, main [role='button'], main [data-control-name]"
        )
        result["edit_candidates"] = await controls.evaluate_all(
            r"""els => {
                const norm = value => (value || '').replace(/\s+/g, ' ').trim();
                const candidates = [];
                for (let i = 0; i < els.length; i += 1) {
                    const el = els[i];
                    const label = norm(el.getAttribute('aria-label'));
                    const title = norm(el.getAttribute('title'));
                    const text = norm(el.innerText || el.textContent);
                    const hay = [label, title, text].join(' ');
                    if (!/\bedit\b/i.test(hay)) continue;

                    let owner = null;
                    let node = el;
                    for (let depth = 0; depth < 9 && node; depth += 1, node = node.parentElement) {
                        const heading = Array.from(node.querySelectorAll(
                            ':scope h2, :scope h3, :scope h4, :scope [role="heading"], :scope [aria-level]'
                        )).find(h => /^about$/i.test(norm(h.innerText || h.textContent)));
                        const ownText = norm(node.innerText || node.textContent);
                        const hasAboutHeading = Boolean(heading);
                        const explicitAbout = /\babout\b/i.test(label + ' ' + title);
                        if (hasAboutHeading || explicitAbout) {
                            owner = node;
                            break;
                        }
                        if (/^about$/i.test(ownText) && ownText.length < 12000) {
                            owner = node.parentElement || node;
                            break;
                        }
                    }
                    if (!owner) continue;
                    const scopeText = norm(owner.innerText || owner.textContent);
                    if (scopeText.length >= 12000 || !/\babout\b/i.test(scopeText + ' ' + label + ' ' + title)) continue;
                    candidates.push({
                        index: i, tag: el.tagName, label, title,
                        text: text.slice(0, 250), aboutScope: true,
                        scopeText: scopeText.slice(0, 700)
                    });
                }
                return candidates.slice(0, 50);
            }"""
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
