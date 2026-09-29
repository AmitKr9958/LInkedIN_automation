from app.browser import (
    PROFILE_LOCK_RETRY_ATTEMPTS,
    PROFILE_LOCK_RETRY_DELAY_SECONDS,
    _is_profile_busy_error,
)


def test_profile_busy_errors_are_retryable():
    assert _is_profile_busy_error(
        RuntimeError("BrowserType.launch: user data directory is already in use")
    )
    assert _is_profile_busy_error(RuntimeError("SingletonLock is present"))
    assert _is_profile_busy_error(RuntimeError("profile is locked"))


def test_non_profile_browser_errors_are_not_retryable():
    assert not _is_profile_busy_error(
        RuntimeError("Executable doesn't exist at C:\\missing\\chrome.exe")
    )


def test_profile_retry_budget_is_bounded():
    assert PROFILE_LOCK_RETRY_ATTEMPTS == 6
    assert PROFILE_LOCK_RETRY_DELAY_SECONDS == 10.0
