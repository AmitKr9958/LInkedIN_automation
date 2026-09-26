from __future__ import annotations

from dataclasses import dataclass, asdict

from ..config import settings
from .parsing import clean_text, dedupe_by


@dataclass
class Notification:
    text: str
    href: str = ""
    category: str = ""

    def to_dict(self):
        return asdict(self)


async def search(page) -> list[Notification]:
    await page.goto(
        f"{settings.linkedin_base_url}/notifications/",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    try:
        await page.wait_for_timeout(2000)
    except Exception:
        pass

    cards = page.locator(
        "main li, main article, "
        "[data-view-name*='notification'], "
        "[class*='notification']"
    )
    out: list[Notification] = []
    try:
        total = min(await cards.count(), 100)
    except Exception:
        total = 0

    for index in range(total):
        card = cards.nth(index)
        try:
            text = clean_text(await card.inner_text())
        except Exception:
            continue
        if not text or len(text) < 3:
            continue
        try:
            hrefs = card.locator("a[href]")
            href = ""
            for j in range(min(await hrefs.count(), 5)):
                candidate = await hrefs.nth(j).get_attribute("href") or ""
                if candidate and not candidate.startswith("#"):
                    href = candidate
                    break
        except Exception:
            href = ""
        lower = text.lower()
        category = "other"
        for name, markers in {
            "job": ("job", "hiring", "career"),
            "connection": ("connected", "connection request", "accepted"),
            "engagement": ("commented", "liked", "mentioned", "reacted"),
            "message": ("message", "inbox"),
        }.items():
            if any(marker in lower for marker in markers):
                category = name
                break
        out.append(Notification(text=text[:1000], href=href, category=category))

    if not out:
        try:
            items = await page.locator("main a[href]").evaluate_all(
                "(els) => els.slice(0,100).map(e => ({text:e.innerText||'',href:e.href||''}))"
            )
        except Exception:
            items = []
        for item in items or []:
            text = clean_text(item.get("text", ""))
            if text:
                out.append(Notification(text=text[:1000], href=item.get("href",""), category="other"))

    return dedupe_by(out, lambda x: (x.href, x.text))
