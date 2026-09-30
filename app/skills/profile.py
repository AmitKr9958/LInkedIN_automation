from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import logging
import re
from urllib.parse import unquote, urlparse

from ..linkedin_reader import current_session_state
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class ProfileSnapshot:
    authenticated: bool
    url: str
    title: str
    name: str = ""
    headline: str = ""
    location: str = ""
    about: str = ""
    experience: str = ""
    skills: str = ""
    featured: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILE_NAME_SELECTORS = (
    "main h1",
    "h1.text-heading-xlarge",
    "h1",
)

PROFILE_HEADLINE_SELECTORS = (
    "div.pv-text-details__left-panel .text-body-medium.break-words",
    "div.pv-text-details__left-panel .text-body-medium",
    "main .text-body-medium.break-words",
    "main .text-body-medium",
    "[data-generated-suggestion-target*='headline']",
    "[class*='headline']",
)

PROFILE_LOCATION_SELECTORS = (
    "div.pv-text-details__left-panel .text-body-small.inline",
    "div.pv-text-details__left-panel .text-body-small.break-words",
    "div.pv-text-details__left-panel .text-body-small",
    "main .text-body-small.inline",
    "main .text-body-small",
    "[data-generated-suggestion-target*='location']",
    "[class*='location']",
    "[class*='text-body-small']",
)

_LOCATION_RE = re.compile(
    r"(?i)\b(?:india|delhi|new delhi|gurgaon|gurugram|noida|jaipur|"
    r"mumbai|bengaluru|bangalore|hyderabad|pune|chennai|kolkata)\b"
)

_PROFILE_NOISE = {
    "1st",
    "2nd",
    "3rd",
    "contact info",
    "followers",
    "connections",
    "open to work",
    "more",
    "message",
    "connect",
    "he/him",
    "she/her",
    "they/them",
    "he him",
    "she her",
    "they them",
}


def _is_valid_headline(text: str, known_name: str = "") -> bool:
    normalized = " ".join((text or "").split())
    if not normalized or normalized.lower() in _PROFILE_NOISE:
        return False
    if known_name and normalized.lower() == known_name.strip().lower():
        return False
    return re.fullmatch(r"(?i)(he|she|they)(?:[/ ](?:him|her|them))?", normalized) is None


async def read_profile(page) -> ProfileSnapshot:
    profile_url = str(settings.profile_url or "").strip()
    if not re.match(r"^https://(?:www\.)?linkedin\.com/in/[^/?#]+/?(?:\?.*)?$", profile_url, re.I):
        raise RuntimeError(
            "PROFILE_URL must point to the authenticated LinkedIn profile, "
            "for example https://www.linkedin.com/in/your-profile-slug/"
        )

    await page.goto(profile_url, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(2_500)
    # LinkedIn lazy-loads profile sections while scrolling. The headed browser
    # may not visibly show a scrollbar, so force a full programmatic scroll.
    await _scroll_profile_to_bottom(page)
    state = await current_session_state(page)

    name_locator = page.locator("main h1, h1.text-heading-xlarge, h1").first
    try:
        await name_locator.wait_for(state="visible", timeout=10_000)
    except Exception:
        pass

    name = await _first_text(page, PROFILE_NAME_SELECTORS)
    headline = await _first_valid_text(page, PROFILE_HEADLINE_SELECTORS, name)
    location = await _first_valid_text(page, PROFILE_LOCATION_SELECTORS, name)

    top_text = await _top_card_text(page)
    if not name:
        name = _name_from_title(state["title"])
    if not headline or not location:
        fallback_name, fallback_headline, fallback_location = _parse_top_card(
            top_text, name
        )
        name = name or fallback_name
        headline = headline or fallback_headline
        location = location or fallback_location

    # Expand read-only "Show all" controls so lazy/condensed sections expose
    # their actual content to the extractor. This only changes the current
    # browser view; it does not edit the LinkedIn profile.
    await _expand_profile_sections(page)

    sections = {
        "about": await _read_profile_section(page, "about"),
        "experience": await _read_profile_section(page, "experience"),
        "skills": await _read_profile_section(page, "skills"),
        "featured": await _read_profile_section(page, "featured"),
    }

    return ProfileSnapshot(
        state["authenticated"],
        state["url"],
        state["title"],
        name,
        headline,
        location,
        sections["about"],
        sections["experience"],
        sections["skills"],
        sections["featured"],
    )


async def _scroll_profile_to_bottom(page, max_rounds: int = 24) -> None:
    last_height = 0
    stable_rounds = 0
    for _ in range(max_rounds):
        try:
            height = await page.evaluate("document.scrollingElement ? document.scrollingElement.scrollHeight : document.body.scrollHeight")
            viewport = await page.evaluate("window.innerHeight || document.documentElement.clientHeight || 0")
            await page.evaluate("window.scrollBy(0, Math.max(600, Math.floor(window.innerHeight * 0.8)))")
            await page.wait_for_timeout(450)
            new_height = await page.evaluate("document.scrollingElement ? document.scrollingElement.scrollHeight : document.body.scrollHeight")
            if new_height <= height and new_height <= last_height:
                stable_rounds += 1
            else:
                stable_rounds = 0
            last_height = max(last_height, new_height)
            scroll_y = await page.evaluate("window.scrollY || window.pageYOffset || 0")
            if viewport and scroll_y + viewport >= new_height - 8 and stable_rounds >= 2:
                break
            if stable_rounds >= 4:
                break
        except Exception:
            break

    try:
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(250)
    except Exception:
        pass


async def _first_text(page, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        loc = page.locator(selector)
        try:
            if await loc.count():
                text = await loc.first.text_content()
                if text and text.strip():
                    return " ".join(text.split())
        except Exception:
            continue
    return ""


async def _first_valid_text(page, selectors: tuple[str, ...], known_name: str = "") -> str:
    for selector in selectors:
        loc = page.locator(selector)
        try:
            count = await loc.count()
            for index in range(min(count, 10)):
                text = " ".join((await loc.nth(index).text_content() or "").split())
                if _is_valid_headline(text, known_name):
                    return text
        except Exception:
            continue
    return ""


def _normalize_section_heading(value: str) -> str:
    """Normalize LinkedIn section headings for tolerant matching."""
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip().lower()


def _section_heading_matches(value: str, section_name: str) -> bool:
    """Return True for exact or decorated LinkedIn section headings."""
    heading = _normalize_section_heading(value)
    wanted = _normalize_section_heading(section_name)
    return bool(heading and wanted and (
        heading == wanted
        or heading.startswith(wanted + " ")
        or heading.startswith(wanted + "(")
    ))


async def _expand_profile_sections(page) -> None:
    """Open read-only profile section expanders when LinkedIn hides content."""
    try:
        await page.evaluate(
            """() => {
                const wanted = /(?:show all|show more|see all)/i;
                const nodes = Array.from(document.querySelectorAll(
                    'main button, main a, main [role="button"]'
                ));
                for (const node of nodes) {
                    const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                    const aria = (node.getAttribute('aria-label') || '').replace(/\\s+/g, ' ').trim();
                    if (!wanted.test(text) && !wanted.test(aria)) continue;
                    try { node.click(); } catch (_) {}
                }
            }"""
        )
        await page.wait_for_timeout(700)
    except Exception:
        pass


_DETAILS_PATHS = {
    "experience": "/details/experience/",
    "skills": "/details/skills/",
    "featured": "/details/featured/",
}
_DETAILS_MAX_CHARS = 12_000
_DETAILS_MIN_CHARS = 40
# Text LinkedIn appends below section content; never part of the section.
_DETAILS_NOISE_MARKERS = (
    "more profiles for you",
    "people you may know",
    "explore premium profiles",
    "you might like",
    "about accessibility",
)
_AUTH_WALL_MARKERS = ("/authwall", "/login", "/checkpoint", "/uas/")


def _profile_slug(profile_url: str) -> str:
    match = re.match(r"^https://(?:www\.)?linkedin\.com/in/([^/?#]+)", str(profile_url or "").strip(), re.I)
    return unquote(match.group(1)).lower() if match else ""


def _details_url_matches(current_url: str, slug: str, section_name: str) -> bool:
    """True only if the browser is on the expected profile's expected details page."""
    if not slug or section_name not in _DETAILS_PATHS:
        return False
    try:
        parsed = urlparse(str(current_url or ""))
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        return False
    path = unquote(parsed.path or "").lower().rstrip("/")
    if any(marker in path for marker in _AUTH_WALL_MARKERS):
        return False
    return path == f"/in/{slug}{_DETAILS_PATHS[section_name].rstrip('/')}"


def _clean_details_text(raw: str) -> str:
    text = " ".join(str(raw or "").split())
    lowered = text.lower()
    cut = len(text)
    for marker in _DETAILS_NOISE_MARKERS:
        idx = lowered.find(marker)
        if idx != -1:
            cut = min(cut, idx)
    return text[:cut].strip()[:_DETAILS_MAX_CHARS]


async def _read_profile_details_page(page, section_name: str) -> str:
    """Read one section from LinkedIn's authenticated /details route (read-only).

    Reuses the existing browser context, opens one temporary tab, validates that
    the final URL is the configured profile's details page, and always closes
    the tab. Returns "" on any failure or when no meaningful content is found.
    """
    if section_name not in _DETAILS_PATHS:
        return ""

    context = getattr(page, "context", None)
    profile_url = str(settings.profile_url or "").strip()
    slug = _profile_slug(profile_url)
    if context is None or not slug:
        return ""

    target_url = f"https://www.linkedin.com/in/{slug}{_DETAILS_PATHS[section_name]}"
    detail_page = None
    try:
        detail_page = await context.new_page()
        await detail_page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
        await detail_page.wait_for_timeout(1_500)

        if not _details_url_matches(str(detail_page.url or ""), slug, section_name):
            logger.warning("Details fallback rejected unexpected URL for %s", section_name)
            return ""

        await _scroll_profile_to_bottom(detail_page, max_rounds=16)
        raw = await detail_page.locator("main").first.inner_text()
        text = _clean_details_text(raw)
        if not text:
            return ""

        extracted = _extract_section_from_text(text, section_name)
        if extracted:
            return extracted

        # Section-scoped page without an explicit heading: the page itself is the scope.
        if len(text) >= _DETAILS_MIN_CHARS:
            return text
    except Exception as exc:
        logger.warning("Details fallback failed for %s: %s", section_name, type(exc).__name__)
        return ""
    finally:
        if detail_page is not None:
            try:
                await detail_page.close()
            except Exception:
                pass
    return ""


async def _read_profile_section(page, section_name: str) -> str:
    """Read one profile section using resilient, read-only DOM extraction."""
    title = _normalize_section_heading(section_name)

    # LinkedIn's profile DOM is client-rendered and its wrapper elements change
    # over time. Find the semantic heading first, then walk to the smallest
    # useful profile-card/container that owns the heading. This avoids relying
    # on generated class names while still returning the actual read-only DOM.
    try:
        value = await page.evaluate(
            """(wanted) => {
                const norm = value => (value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                const matches = value => {
                    const text = norm(value);
                    return text === wanted ||
                        text.startsWith(wanted + ' ') ||
                        text.startsWith(wanted + '(');
                };

                const headingSelector = [
                    'main h1', 'main h2', 'main h3',
                    'main [role="heading"]', 'main [aria-level]',
                ].join(', ');
                const headings = Array.from(document.querySelectorAll(headingSelector));
                let heading = headings.find(h => matches(h.textContent));

                // Some LinkedIn layouts use a plain div/span as the section title.
                // Accept short leaf elements whose complete text is the heading.
                if (!heading) {
                    // LinkedIn often renders section titles as a button/div/span
                    // containing nested spans. Match complete rendered text.
                    const candidates = Array.from(document.querySelectorAll('main *'))
                        .filter(el => {
                            const text = norm(el.textContent);
                            if (!matches(text)) return false;
                            const tag = (el.tagName || '').toLowerCase();
                            return tag !== 'main' && tag !== 'body' && tag !== 'section';
                        })
                        .sort((a, b) => {
                            const depth = el => {
                                let n = 0, node = el;
                                while (node && node !== document.body) {
                                    n += 1;
                                    node = node.parentElement;
                                }
                                return n;
                            };
                            return depth(b) - depth(a);
                        });
                    heading = candidates[0] || null;
                }
                if (!heading) return '';

                // Prefer stable profile-card boundaries before generic parents.
                const stable = heading.closest(
                    'section, [data-view-name], .artdeco-card, [class*="pv-profile-card"]'
                );
                if (stable) {
                    const text = (stable.innerText || '').replace(/\\s+/g, ' ').trim();
                    if (text.length > wanted.length + 8) return text;
                }

                // Otherwise climb until the container contains meaningful content.
                let node = heading.parentElement;
                let best = '';
                for (let i = 0; i < 8 && node; i += 1) {
                    const text = (node.innerText || '').replace(/\\s+/g, ' ').trim();
                    if (text.length > wanted.length + 8 && text.length < 30000) {
                        best = text;
                        // Stop at a likely card boundary; otherwise keep the
                        // smallest useful ancestor discovered so far.
                        const tag = (node.tagName || '').toLowerCase();
                        if (tag === 'section' || node.getAttribute('data-view-name')) {
                            break;
                        }
                    }
                    node = node.parentElement;
                }
                return best;
            }""",
            title,
        )
        value = " ".join(str(value or "").split())
        if value and len(value) > len(title) + 8:
            return value
    except Exception:
        pass

    # Fallback 1: LinkedIn exposes stable details URLs even when section
    # headings are wrapped in generated markup. Recover the owning profile card
    # without depending on generated CSS class names.
    details_hrefs = {
        "experience": "/details/experience",
        "skills": "/details/skills",
        "featured": "/details/featured",
    }
    href = details_hrefs.get(section_name)
    if href:
        try:
            links = page.locator(f'main a[href*="{href}"]')
            count = await links.count()
            for index in range(min(count, 5)):
                link = links.nth(index)
                value = await link.evaluate(
                    """el => {
                        const candidates = [];
                        let node = el;
                        for (let i = 0; i < 8 && node; i += 1, node = node.parentElement) {
                            const text = (node.innerText || '').replace(/\\s+/g, ' ').trim();
                            if (text && text.length > 20 && text.length < 30000) candidates.push(text);
                            if ((node.tagName || '').toLowerCase() === 'section') break;
                        }
                        return candidates.sort((a, b) => a.length - b.length)[0] || '';
                    }"""
                )
                value = " ".join(str(value or "").split())
                if value and len(value) > len(title) + 8:
                    return value
        except Exception:
            pass

    # Fallback 2: scan the rendered main text. This handles LinkedIn layouts
    # where the section title is a nested button/div/span rather than a semantic
    # heading. We only accept an exact section-title line and stop at the next
    # known profile section, so we do not accidentally return the whole page.
    try:
        raw = await page.locator("main").first.inner_text()
        extracted = _extract_section_from_text(raw, section_name)
        if extracted:
            return extracted
    except Exception:
        pass

    # Fallback 3: authenticated, section-specific details page (one temp tab).
    # Some layouts expose only a link/card on the main page; the real content
    # lives on /details/<section>/.
    if section_name in _DETAILS_PATHS:
        value = await _read_profile_details_page(page, section_name)
        if value:
            return value

    # Fallback 4: explicit IDs/ARIA/data attributes used by older and
    # accessibility-oriented LinkedIn markup.
    selectors = (
        f"main section#{section_name}",
        f"main div#{section_name}",
        f"main [data-section='{section_name}']",
        f"main [data-section-id='{section_name}']",
        f"main [aria-label*='{section_name}' i]",
        f"main a[href$='#{section_name}']",
        f"main [id*='-{section_name}-']",
    )
    for selector in selectors:
        loc = page.locator(selector).first
        try:
            if await loc.count():
                text = " ".join((await loc.inner_text()).split())
                if text and len(text) > len(title) + 8:
                    return text
        except Exception:
            continue

    return ""


_PROFILE_SECTION_ORDER = ("about", "experience", "education", "skills", "featured")


def _extract_section_from_text(raw_text: str, section_name: str) -> str:
    """Extract one profile section from rendered text when DOM wrappers vary."""
    lines = [
        " ".join(line.replace("\u00a0", " ").split()).strip()
        for line in str(raw_text or "").splitlines()
    ]
    lines = [line for line in lines if line]
    wanted = _normalize_section_heading(section_name)

    # Normal innerText normally preserves one heading per line.
    for index, line in enumerate(lines):
        if _section_heading_matches(line, wanted):
            content = []
            for candidate in lines[index:]:
                normalized = _normalize_section_heading(candidate)
                if content and normalized in _PROFILE_SECTION_ORDER:
                    break
                content.append(candidate)
            value = " ".join(content).strip()
            if len(value) > len(wanted) + 8:
                return value

    # Some Chromium/LinkedIn layouts flatten large parts of the page into a
    # single line. In that case, locate the requested heading in the normalized
    # text and stop at the next known section heading.
    flat = " ".join(lines).strip()
    if not flat:
        return ""

    section_positions = {
        section: [
            match.start()
            for match in re.finditer(
                rf"(?<!\w){re.escape(section)}"
                rf"(?:\s*\(\s*\d+\s*\)|\s+\d+)?(?!\w)",
                flat,
                re.I,
            )
        ]
        for section in _PROFILE_SECTION_ORDER
    }
    starts = section_positions.get(wanted, [])
    if not starts:
        return ""

    start = starts[0]
    following = [
        position
        for section, positions in section_positions.items()
        if section != wanted
        for position in positions
        if position > start
    ]
    end = min(following) if following else len(flat)
    value = flat[start:end].strip()
    return value if len(value) > len(wanted) + 8 else ""

async def _top_card_text(page) -> str:
    for selector in (
        "main",
        "section[data-member-id]",
        "main section",
    ):
        loc = page.locator(selector).first
        try:
            if await loc.count():
                text = await loc.inner_text()
                if text and text.strip():
                    return text
        except Exception:
            continue
    return ""


def _parse_top_card(raw_text: str, known_name: str) -> tuple[str, str, str]:
    lines = [" ".join(x.split()) for x in raw_text.splitlines() if x.strip()]
    lines = [x for x in lines if x.lower() not in _PROFILE_NOISE]

    name = known_name.strip()
    if not name:
        for line in lines[:15]:
            if 2 <= len(line.split()) <= 5 and not _LOCATION_RE.search(line):
                name = line
                break

    name_index = next(
        (i for i, line in enumerate(lines) if line.lower() == name.lower()),
        -1,
    )

    candidates = lines[name_index + 1 :] if name_index >= 0 else lines[:20]
    headline = ""
    location = ""

    for line in candidates[:20]:
        lower = line.lower()
        if lower == name.lower() or lower in _PROFILE_NOISE:
            continue
        if _LOCATION_RE.search(line):
            location = line
            continue
        if not headline and 2 <= len(line) <= 180:
            if not re.search(r"\b(followers?|connections?|experience|education)\b", lower):
                if _is_valid_headline(line, name):
                    headline = line
        if headline and location:
            break

    return name, headline, location


def _name_from_title(title: str) -> str:
    suffix = " | LinkedIn"
    if title.endswith(suffix):
        candidate = title[: -len(suffix)].strip()
        if candidate and candidate.lower() not in {"linkedin", "feed"}:
            return candidate
    return ""
