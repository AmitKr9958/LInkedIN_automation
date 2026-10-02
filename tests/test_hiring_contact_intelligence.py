from app.drafting import hiring_contact_message
from app.outreach import build_outreach_plan, classify_target, score_target


def test_contact_classification_is_not_recruiter_only():
    assert classify_target("Engineering Manager, Business Intelligence") == "hiring_manager"
    assert classify_target("Head of Data Analytics") == "business_leader"
    assert classify_target("Director, Business Intelligence") == "business_leader"
    assert classify_target("Talent Acquisition Partner") == "recruiter"


def test_job_and_company_evidence_can_qualify_non_recruiter():
    people = [
        {
            "name": "Anita Sharma",
            "headline": "Engineering Manager - Data & Analytics",
            "company": "Acme",
            "location": "Gurugram, India",
            "href": "https://www.linkedin.com/in/anita",
            "text": "Engineering Manager - Data & Analytics at Acme",
        },
        {
            "name": "Generic HR",
            "headline": "HR",
            "location": "Gurugram, India",
            "href": "https://www.linkedin.com/in/generic-hr",
            "text": "HR",
        },
    ]
    job = {
        "title": "Power BI Developer",
        "company": "Acme",
        "location": "Gurugram, India",
        "url": "https://www.linkedin.com/jobs/view/1",
    }
    targets = build_outreach_plan(people, job)
    assert len(targets) == 1
    assert targets[0].name == "Anita Sharma"
    assert targets[0].target_type in {"hiring_manager", "domain_leader"}
    assert targets[0].relevance_score >= 4
    assert any("company evidence" in signal for signal in targets[0].matching_signals)


def test_generic_recruiter_title_without_job_or_company_evidence_is_not_enough():
    target = score_target(
        {
            "name": "Generic Recruiter",
            "headline": "Recruiter",
            "text": "Recruiter",
        },
        job_title="Power BI Developer",
        company="Acme",
    )
    assert target.relevance_score < 4


def test_hiring_contact_message_is_job_specific():
    draft = hiring_contact_message(
        "Anita Sharma",
        "Power BI Developer",
        "Acme",
        "hiring_manager",
        "company evidence: Acme; domain evidence: data analytics",
        ["Power BI", "SQL", "Data Analytics"],
    )
    assert "Power BI Developer" in draft.text
    assert "Acme" in draft.text
    assert "Anita" in draft.text
    assert "relevance" not in draft.text.lower()


def test_people_can_be_associated_with_fresh_job_evidence():
    from app.outreach import associate_people_with_jobs

    people = [
        {
            "name": "Anita Sharma",
            "headline": "Talent Acquisition - Data & Analytics",
            "company": "Acme",
            "location": "Gurugram, India",
            "href": "https://www.linkedin.com/in/anita",
            "text": "Talent Acquisition hiring Data & Analytics at Acme",
        },
        {
            "name": "Generic Recruiter",
            "headline": "Recruiter",
            "company": "Other Co",
            "location": "Gurugram, India",
            "href": "https://www.linkedin.com/in/generic",
            "text": "Recruiter",
        },
    ]
    jobs = [
        {
            "title": "Power BI Developer",
            "company": "Acme",
            "location": "Gurugram, India",
            "url": "https://www.linkedin.com/jobs/view/123",
            "posted": "2 hours ago",
        }
    ]

    rows = associate_people_with_jobs(people, jobs)
    assert rows[0]["associated_jobs"][0]["association"] == "company_match"
    assert rows[0]["associated_jobs"][0]["job"]["url"].endswith("/123")
    assert rows[1]["associated_jobs"] == []
