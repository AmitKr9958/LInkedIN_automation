from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


async def scroll_page_completely(page, *, max_rounds: int = 12, pause_ms: int = 700) -> int:
    """Bounded end-of-page scroll for non-virtualized content."""
    rounds = 0
    stable_rounds = 0
    previous = None
    for _ in range(max_rounds):
        try:
            state = await page.evaluate(
                """() => {
                    const elements = [document.scrollingElement, ...Array.from(document.querySelectorAll('main, main *'))];
                    let containers = 0, moved = 0;
                    const seen = new Set();
                    for (const el of elements) {
                        if (!el || seen.has(el)) continue;
                        seen.add(el);
                        const style = getComputedStyle(el);
                        if (el.scrollHeight > el.clientHeight + 40 && /(auto|scroll)/.test(style.overflowY)) {
                            containers++;
                            const before = el.scrollTop;
                            el.scrollTop = el.scrollHeight;
                            if (el.scrollTop !== before) moved++;
                        }
                    }
                    const root = document.scrollingElement || document.documentElement;
                    const before = root.scrollTop;
                    window.scrollTo(0, root.scrollHeight);
                    if (root.scrollTop !== before) moved++;
                    return {height: root.scrollHeight, top: root.scrollTop, containers, moved};
                }"""
            )
        except Exception:
            break
        rounds += 1
        geometry = (state.get("height", 0), state.get("top", 0), state.get("containers", 0), state.get("moved", 0))
        stable_rounds = stable_rounds + 1 if previous == geometry or state.get("moved", 0) == 0 else 0
        previous = geometry
        if stable_rounds >= 2:
            break
        try:
            await page.wait_for_timeout(pause_ms)
        except Exception:
            pass
    return rounds


async def scroll_and_capture(
    page,
    capture: Callable[[], Awaitable[list[Any]]],
    *,
    max_rounds: int = 24,
    pause_ms: int = 700,
    stable_rounds: int = 3,
) -> tuple[list[Any], int]:
    """Incrementally scroll while capturing virtualized results.

    LinkedIn can remove earlier cards from the DOM while scrolling. A caller
    therefore supplies a capture callback which runs before scrolling and after
    every bounded incremental step. Records are deduplicated by href/key.
    """
    records: list[Any] = []
    seen: set[str] = set()
    no_progress = 0
    rounds = 0
    last_geometry: tuple[int, int, int] | None = None

    async def collect() -> None:
        nonlocal records
        try:
            batch = await capture()
        except Exception:
            return
        for item in batch or []:
            if isinstance(item, dict):
                key = str(item.get("href") or item.get("key") or "").strip().lower()
            else:
                key = str(getattr(item, "href", "") or getattr(item, "key", "") or "").strip().lower()
            if not key:
                key = f"__record__{len(records)}"
            if key not in seen:
                seen.add(key)
                records.append(item)

    await collect()
    for _ in range(max_rounds):
        try:
            state = await page.evaluate(
                """() => {
                    const root = document.scrollingElement || document.documentElement;
                    const beforeRoot = root.scrollTop;
                    const rootStep = Math.max(300, Math.floor(root.clientHeight * 0.82));
                    let moved = 0;
                    const seen = new Set();
                    for (const el of [root, ...Array.from(document.querySelectorAll('main, main *'))]) {
                        if (!el || seen.has(el)) continue;
                        seen.add(el);
                        const style = getComputedStyle(el);
                        if (el.scrollHeight <= el.clientHeight + 40 || !/(auto|scroll)/.test(style.overflowY)) continue;
                        const before = el.scrollTop;
                        el.scrollTop = Math.min(el.scrollTop + Math.max(250, Math.floor(el.clientHeight * 0.82)), el.scrollHeight);
                        if (el.scrollTop !== before) moved++;
                    }
                    window.scrollBy(0, rootStep);
                    if (root.scrollTop !== beforeRoot) moved++;
                    return {
                        height: root.scrollHeight,
                        top: root.scrollTop,
                        viewport: root.clientHeight,
                        moved,
                        atEnd: root.scrollTop + root.clientHeight >= root.scrollHeight - 8
                    };
                }"""
            )
        except Exception:
            break
        rounds += 1
        try:
            await page.wait_for_timeout(pause_ms)
        except Exception:
            pass
        before_count = len(records)
        await collect()
        geometry = (int(state.get("height", 0)), int(state.get("top", 0)), int(state.get("moved", 0)))
        if len(records) == before_count and (geometry == last_geometry or not state.get("moved", 0)):
            no_progress += 1
        else:
            no_progress = 0
        last_geometry = geometry
        if state.get("atEnd") and no_progress >= 1:
            break
        if no_progress >= stable_rounds:
            break
    return records, rounds
