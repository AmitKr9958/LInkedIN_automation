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
    "a[href*='/feed/']",
    "nav[aria-label*='Primary']",
]

JOB_CARD_SELECTORS = [
    "li.jobs-search-results__list-item",
    ".job-card-container",
    "[data-occludable-job-id]",
]

PROFILE_MARKERS = [
    "a[href*='/mynetwork/']",
    "button[aria-label*='profile']",
]

AUTHENTICATED_MARKERS = [
    "[data-view-name='feed']",
    "a[href*='/feed/']",
    "button[aria-label*='Me']",
]
