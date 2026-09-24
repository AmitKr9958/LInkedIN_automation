"""Centralized selectors; keep UI-specific changes isolated here."""

LOGIN_MARKERS = [
    "input[name='session_key']",
    "input[name='session_password']",
    "input[autocomplete='username']",
    "input[autocomplete='current-password']",
    "form[action*='/login']",
]

FEED_MARKERS = [
    "[data-view-name='feed']",
    "main[role='main']",
    "div[role='main']",
    "nav[aria-label*='Primary']",
    "a[href*='/feed/']",
]

JOB_CARD_SELECTORS = [
    "li.jobs-search-results__list-item",
    ".job-card-container",
    "[data-occludable-job-id]",
]

PROFILE_MARKERS = [
    "a[href*='/in/']",
    "a[href*='/mynetwork/']",
    "button[aria-label*='profile']",
    "main[role='main']",
]
