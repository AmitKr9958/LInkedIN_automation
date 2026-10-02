from app.profile_optimizer import audit_profile, generate_profile_optimization


def test_profile_audit_identifies_missing_sections_and_keywords():
    report = audit_profile({
        "headline": "BI Developer",
        "about": "",
        "experience": "Built Power BI dashboards using SQL and DAX; reduced refresh time by 20%.",
        "skills": "Power BI, SQL, DAX",
        "featured": "",
    })
    assert 0 <= report["score"] <= 100
    assert report["section_scores"]["headline"] < 100
    assert "about" in {item["section"] for item in report["findings"]}
    assert "featured" in {item["section"] for item in report["findings"]}
    assert "Power BI" in report["matched_keywords"]


def test_profile_optimizer_is_deterministic_without_llm():
    profile = {
        "url": "https://www.linkedin.com/in/example/",
        "headline": "Senior Power BI Developer | SQL | DAX",
        "about": "Power BI professional with measurable delivery: reduced manual workload by 30%.",
        "experience": "Automated Power BI reporting and improved refresh time by 20%.",
        "skills": "Power BI, SQL, DAX, Power Query",
        "featured": "Dashboard portfolio",
    }
    report = generate_profile_optimization(profile, use_llm=False)
    assert report.llm_used is False
    assert report.drafts == {}
    assert report.score > 0
    assert "Power BI" in report.matched_keywords


def test_profile_optimizer_rejects_new_numeric_claims(monkeypatch):
    profile = {
        "headline": "Power BI Developer",
        "about": "Reduced manual workload by 30%.",
        "experience": "Improved refresh time by 20%.",
        "skills": "Power BI, SQL",
        "featured": "",
    }

    def fake_chat_json(**kwargs):
        return {
            "drafts": {
                "headline": "Power BI Developer | 99% faster",
                "about": "I reduced manual workload by 30%.",
                "experience": "Improved refresh time by 20%.",
            }
        }

    monkeypatch.setattr("app.profile_optimizer.is_configured", lambda: True)
    monkeypatch.setattr("app.profile_optimizer.chat_json", fake_chat_json)
    report = generate_profile_optimization(profile, use_llm=True)
    assert report.llm_used is True
    assert "headline" not in report.drafts
    assert "30%" in report.drafts["about"]


def test_profile_optimizer_bounds_generated_sections(monkeypatch):
    profile = {
        "headline": "Power BI Developer",
        "about": "Power BI and SQL.",
        "experience": "Built Power BI dashboards.",
        "skills": "Power BI, SQL",
        "featured": "",
    }

    def fake_chat_json(**kwargs):
        return {"drafts": {"headline": "x" * 221, "about": "ok", "experience": "ok"}}

    monkeypatch.setattr("app.profile_optimizer.is_configured", lambda: True)
    monkeypatch.setattr("app.profile_optimizer.chat_json", fake_chat_json)
    report = generate_profile_optimization(profile, use_llm=True)
    assert "headline" not in report.drafts
    assert report.drafts["about"] == "ok"
    assert report.drafts["experience"] == "ok"


def test_profile_audit_recognizes_verified_metrics_and_action_language():
    report = audit_profile({
        "headline": "Senior Power BI Developer | SQL | DAX",
        "about": "Power BI professional. Reduced manual workload by 30%.",
        "experience": "Automated reporting and improved refresh time by 20%.",
        "skills": "Power BI, SQL, DAX",
        "featured": "Dashboard portfolio",
    })
    assert not any(
        item["issue"] == "add quantified outcomes that are already true"
        for item in report["findings"]
    )
    assert not any(
        item["issue"] == "experience lacks quantified outcomes"
        for item in report["findings"]
    )


def test_profile_optimizer_ai_receives_full_target_context(monkeypatch):
    profile = {
        "headline": "Power BI Developer | SQL | DAX",
        "about": "Power BI professional with 30% workload reduction.",
        "experience": "Automated reporting and improved refresh time by 20%.",
        "skills": "Power BI, SQL, DAX, Power Query",
        "featured": "Dashboard portfolio",
    }
    captured = {}

    def fake_chat_json(**kwargs):
        captured["system"] = kwargs["system"]
        captured["user"] = kwargs["user"]
        return {
            "positioning": "Power BI professional focused on reporting automation.",
            "priority_actions": ["Clarify measurable business impact."],
            "keyword_strategy": ["Power BI", "DAX", "SQL"],
            "section_notes": {"headline": "Lead with target role and core stack."},
            "drafts": {
                "headline": "Power BI Developer | SQL | DAX",
                "about": "Power BI professional with 30% workload reduction.",
                "experience": "Automated reporting and improved refresh time by 20%.",
            },
        }

    monkeypatch.setattr("app.profile_optimizer.is_configured", lambda: True)
    monkeypatch.setattr("app.profile_optimizer.chat_json", fake_chat_json)
    report = generate_profile_optimization(profile, use_llm=True)

    assert report.llm_used is True
    assert "senior AI strategist" in captured["system"]
    assert "target_roles" in captured["user"]
    assert "target_locations" in captured["user"]
    assert report.drafts["headline"]


from app.profile_optimizer import profile_fingerprint


def test_profile_fingerprint_changes_when_profile_changes():
    profile = {
        "url": "https://www.linkedin.com/in/example/", "name": "Example",
        "headline": "Power BI Developer", "location": "Delhi", "about": "SQL DAX",
        "experience": "Built dashboards", "skills": "Power BI", "featured": "Project",
    }
    first = profile_fingerprint(profile)
    assert first != profile_fingerprint(dict(profile, headline="Senior Power BI Developer"))
    assert first == profile_fingerprint(dict(profile))


def test_profile_audit_does_not_apply_per_entry_experience_limit_to_aggregate():
    report = audit_profile({
        "headline": "Senior Power BI Developer | SQL | DAX",
        "about": "Power BI professional with 30% workload reduction.",
        "experience": "Built Power BI dashboards using SQL and DAX; " + ("Automated reporting. " * 160),
        "skills": "Power BI, SQL, DAX, Power Query",
        "featured": "Dashboard portfolio",
    })
    assert not any(item["issue"] == "experience content is unusually long" for item in report["findings"])
    assert report["optimization_signals"]["experience_is_aggregate_snapshot"] is True


def test_profile_audit_exposes_linkedin_profile_signals():
    report = audit_profile({
        "headline": "Senior Power BI Developer | SQL | DAX",
        "about": "Power BI professional with 30% workload reduction.",
        "experience": "Automated reporting and improved refresh time by 20%.",
        "skills": "Power BI, SQL, DAX",
        "featured": "",
    })
    signals = report["optimization_signals"]
    assert signals["headline_characters"] == len("Senior Power BI Developer | SQL | DAX")
    assert signals["headline_limit"] == 220
    assert signals["about_limit"] == 2600
    assert signals["featured_is_optional_evidence_section"] is True
