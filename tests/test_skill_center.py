import asyncio

from app.skill_center import run_skill, skill_catalog


def test_skill_center_exposes_all_registered_skills():
    catalog = skill_catalog()
    assert len(catalog) == 28
    assert {item["name"] for item in catalog} == {
        item.name for item in __import__("app.skill_registry", fromlist=["list_skills"]).list_skills()
    }


def test_local_skill_execution():
    result = asyncio.run(
        run_skill(
            "post_writer",
            {"topic": "Power BI", "angle": "How automation reduced manual reporting effort"},
        )
    )
    assert result["kind"] == "post"
    assert "Power BI" in result["text"]


def test_approval_skill_does_not_execute_linkedin_action():
    result = asyncio.run(
        run_skill(
            "messaging",
            {"target": "manual-review", "payload": "Draft message for review"},
        )
    )
    assert result["mode"] == "approval"
    assert result["status"] == "pending_approval"
    assert result["approval_id"]
