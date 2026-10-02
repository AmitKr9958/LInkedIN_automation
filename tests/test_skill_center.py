import asyncio

from app.skill_center import run_skill, skill_catalog


def test_skill_center_exposes_all_registered_skills():
    catalog = skill_catalog()
    assert len(catalog) == len(__import__("app.skill_registry", fromlist=["list_skills"]).list_skills())
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


def test_remote_india_uses_workplace_filter():
    from app.skills.jobs import _build_jobs_search_url, _location_matches_requested
    url = _build_jobs_search_url("Power BI", "Remote India")
    assert "location=India" in url
    assert "f_WT=2" in url
    assert _location_matches_requested("India (Remote)", "Remote India")
    assert not _location_matches_requested("Gurgaon, Haryana, India", "Remote India")

def test_profile_optimizer_is_ai_ready_and_live_by_default():
    item = next(x for x in skill_catalog() if x["name"] == "profile_optimizer")
    source = next(x for x in item["fields"] if x["name"] == "source")
    assert source["type"] == "select"
    assert source["default"] == "live"
    assert source["options"] == ["live", "manual"]


def test_profile_optimizer_keeps_read_only_audit_when_llm_returns_non_json(monkeypatch):
    import app.skill_center as skill_center

    def fail_llm(**kwargs):
        from app.llm_client import LLMError
        raise LLMError("LLM returned non-JSON content for a JSON-only request after recovery retry")

    monkeypatch.setattr(skill_center, "chat_json", fail_llm)
    result = asyncio.run(
        skill_center.run_skill(
            "profile_optimizer",
            {
                "source": "manual",
                "profile": '{"name":"Amit","headline":"Power BI Developer","about":"Power BI SQL DAX","experience":"Built dashboards","skills":"Power BI SQL","featured":"Project"}',
            },
        )
    )
    assert result["source"] == "manual"
    assert result["readable_result"]["section_audit"]["Headline"] == "Found"
    assert result["readable_result"]["section_audit"]["About"] == "Found"
    assert result["readable_result"]["ai_error"]
    assert "no LinkedIn profile changes were made" in result["message"]  # read-only safety contract


def test_profile_optimizer_grounds_every_headline_option(monkeypatch):
    import app.skill_center as skill_center

    def fake_llm(**kwargs):
        return {
            "overall_assessment": "Test",
            "strengths": [],
            "missing_information": [],
            "headline_options": [
                "Power BI Developer | 10 years | DAX | SQL",
                "Certified Tableau Architect | 25 years",
                "Power BI Developer | Microsoft Fabric",
            ],
            "about_draft": "",
            "experience_improvements": [],
            "skills_to_highlight": [],
            "featured_recommendations": [],
            "keyword_strategy": [],
            "next_actions": [],
        }

    monkeypatch.setattr(skill_center, "chat_json", fake_llm)
    result = asyncio.run(
        skill_center.run_skill(
            "profile_optimizer",
            {
                "source": "manual",
                "profile": '{"name":"Amit","headline":"Power BI Developer | 10 years","about":"Power BI SQL DAX","experience":"Built dashboards","skills":"Power BI SQL Microsoft Fabric","featured":""}',
            },
        )
    )
    grounding = result["source_grounding"]
    assert len(grounding["headline_options"]) == 3
    assert grounding["headline_options"][0]["status"] == "safe"
    assert grounding["headline_options"][1]["status"] == "blocked"
    assert grounding["publishable"] is False
