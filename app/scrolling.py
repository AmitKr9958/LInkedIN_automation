from __future__ import annotations

async def scroll_page_completely(page, *, max_rounds: int = 12, pause_ms: int = 700) -> int:
    """Scroll the window and discovered scrollable containers toward their end.

    LinkedIn uses both document scrolling and virtualized inner result panes.
    This deliberately does not attempt to bypass lazy-loading/security controls:
    it only performs ordinary user-equivalent scrolling and stops at a bounded
    number of rounds or when the scrollable geometry becomes stable.
    """
    rounds = 0
    stable_rounds = 0
    previous = None
    for _ in range(max_rounds):
        try:
            state = await page.evaluate(
                """() => {
                    const elements = [document.scrollingElement, ...Array.from(document.querySelectorAll('main, main *'))];
                    let containers = 0;
                    let moved = 0;
                    const seen = new Set();
                    for (const el of elements) {
                        if (!el || seen.has(el)) continue;
                        seen.add(el);
                        const style = getComputedStyle(el);
                        const scrollable = el.scrollHeight > el.clientHeight + 40 &&
                            /(auto|scroll)/.test(style.overflowY);
                        if (scrollable) {
                            containers++;
                            const before = el.scrollTop;
                            el.scrollTop = el.scrollHeight;
                            if (el.scrollTop !== before) moved++;
                        }
                    }
                    const root = document.scrollingElement || document.documentElement;
                    const beforeWindow = root.scrollTop;
                    window.scrollTo(0, root.scrollHeight);
                    const windowMoved = root.scrollTop !== beforeWindow ? 1 : 0;
                    return {
                        height: root.scrollHeight,
                        top: root.scrollTop,
                        containers,
                        moved: moved + windowMoved
                    };
                }"""
            )
        except Exception:
            break
        rounds += 1
        geometry = (
            state.get("height", 0),
            state.get("top", 0),
            state.get("containers", 0),
            state.get("moved", 0),
        )
        if previous == geometry or state.get("moved", 0) == 0:
            stable_rounds += 1
        else:
            stable_rounds = 0
        previous = geometry
        if stable_rounds >= 2:
            break
        try:
            await page.wait_for_timeout(pause_ms)
        except Exception:
            pass
    return rounds
