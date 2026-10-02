import asyncio

import pytest

from app.profile_grounding import validate_profile_drafts
from app.profile_writer import ProfileWriteError, apply_approved_profile_proposal


def _profile():
    return {
        "name": "Amit Kumar",
        "headline": "Senior Power BI Developer | DAX | SQL | Power Query | 10 years",
        "about": "Delivered 40+ dashboards and reduced reporting effort by 30%. DP-600 in progress.",
        "experience": "Led Power BI work and improved query speed by 75%.",
        "skills": "Power BI, DAX, SQL, Power Query, Microsoft Fabric",
        "featured": "",
    }


def test_grounding_allows_source_supported_facts():
    result = validate_profile_drafts(
        _profile(),
        {
            "headline": "Senior Power BI Developer | DAX | SQL | 10 years",
            "about": "Delivered 40+ dashboards and reduced reporting effort by 30%.",
            "experience": "Improved query speed by 75%.",
        },
    )
    assert result["publishable"] is True
    assert all(item["status"] != "blocked" for item in result["fields"].values())


def test_grounding_blocks_new_numeric_claims():
    result = validate_profile_drafts(
        _profile(),
        {
            "about": "Reduced report latency from 8 seconds to 2 seconds and prevented 15% data discrepancies.",
        },
    )
    assert result["publishable"] is False
    issues = result["fields"]["about"]["issues"]
    assert any(issue["type"] == "unsupported_numbers" for issue in issues)
    values = {value for issue in issues for value in issue.get("values", [])}
    assert "2" in values
    assert "15%" in values


def test_grounding_blocks_new_certification_and_technology_claims():
    result = validate_profile_drafts(
        _profile(),
        {
            "about": "Expert in Tableau and certified PL-300 professional.",
        },
    )
    assert result["publishable"] is False
    issue_types = {issue["type"] for issue in result["fields"]["about"]["issues"]}
    assert "unsupported_certifications" in issue_types
    assert "unsupported_technologies" in issue_types


def test_profile_writer_rejects_ungrounded_approved_proposal_before_browser(monkeypatch):
    monkeypatch.setattr("app.profile_writer.settings.linkedin_profile_write_enabled", True)
    monkeypatch.setattr("app.profile_writer.settings.dry_run", False)
    monkeypatch.setattr("app.profile_writer.settings.profile_url", "https://www.linkedin.com/in/example/")
    proposal = {
        "profile_fingerprint": "expected",
        "profile": _profile(),
        "drafts": {
            "about": "Reduced report latency from 8 seconds to 2 seconds and prevented 15% data discrepancies.",
        },
    }
    with pytest.raises(ProfileWriteError, match="source-grounding validation"):
        asyncio.run(apply_approved_profile_proposal(proposal))

# Source-grounding regression coverage remains intentionally deterministic.
