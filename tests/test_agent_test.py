from pathlib import Path
from tempfile import TemporaryDirectory

from app.agent_test import run_agent_contract_test, run_safe_workflow_test
from app.application_tracker import ApplicationTracker
from app.approval_queue import ApprovalQueue


def test_agent_contract_test_covers_registered_skills():
    results = run_agent_contract_test()
    assert any(r.skill == "skill-registry" and r.ok for r in results)
    assert all(r.ok for r in results)
    assert any(r.skill == "post_writer" for r in results)
    assert any(r.skill == "story_bank" for r in results)


def test_safe_end_to_end_workflow():
    results = run_safe_workflow_test()
    assert all(result.ok for result in results)


def test_sqlite_connections_are_closed_for_temp_cleanup():
    with TemporaryDirectory() as tmp:
        tracker = ApplicationTracker(Path(tmp) / "applications.sqlite3")
        tracker.add("https://example.test/job", "Test", "Example")
        tracker.transition("https://example.test/job", "shortlisted")

        queue = ApprovalQueue(str(Path(tmp) / "approvals.sqlite3"))
        queue.add("test_action", "https://example.test/job", '{"ok": true}')
        assert queue.list_pending()

    assert not Path(tmp).exists()
