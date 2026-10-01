from app.browser import (
    PROFILE_LOCK_RETRY_ATTEMPTS,
    PROFILE_LOCK_RETRY_DELAY_SECONDS,
    _is_chromium_startup_timeout,
    _is_profile_busy_error,
    CHROMIUM_START_RETRY_ATTEMPTS,
    CHROMIUM_START_RETRY_DELAY_SECONDS,
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


def test_chromium_startup_timeout_is_retryable_but_missing_executable_is_not():
    assert _is_chromium_startup_timeout(
        RuntimeError("BrowserType.launch_persistent_context: Timeout 45000ms exceeded")
    )
    assert not _is_chromium_startup_timeout(
        RuntimeError(
            "BrowserType.launch_persistent_context: Executable doesn't exist at "
            r"C:\missing\chrome.exe"
        )
    )


def test_chromium_startup_retry_budget_is_bounded():
    assert CHROMIUM_START_RETRY_ATTEMPTS == 3
    assert CHROMIUM_START_RETRY_DELAY_SECONDS == 5.0
