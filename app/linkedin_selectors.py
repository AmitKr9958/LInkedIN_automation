"""Centralized selectors; keep UI-specific changes isolated here."""

LOGIN_MARKERS = [
    "input[name='session_key']",
    "input[name='session_password']",
    "button[type='submit']",
]

FEED_MARKERS = [
    "main",
    "[data-view-name='feed']",
]

JOB_CARD_SELECTORS = [
    "li.jobs-search-results__list-item",
    ".job-card-container",
    "[data-occludable-job-id]",
]

PROFILE_MARKERS = [
    "main",
    "section",
]
