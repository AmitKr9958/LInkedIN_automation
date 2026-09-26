from app.agent_test import run_agent_contract_test


def test_agent_contract_test_covers_registered_skills():
    results = run_agent_contract_test()
    assert any(r.skill == "skill-registry" and r.ok for r in results)
    assert all(r.ok for r in results)
    assert any(r.skill == "post_writer" for r in results)
    assert any(r.skill == "story_bank" for r in results)


from app.agent_test import run_safe_workflow_test


def test_safe_end_to_end_workflow():
    results = run_safe_workflow_test()
    assert all(result.ok for result in results)
