from app.outreach import OutreachTarget, build_outreach_plan, classify_target, draft_connection, draft_followup, score_target


class Person:
    name = "Recruiter One"
    headline = "Senior Technical Recruiter at Example"
    href = "https://www.linkedin.com/in/recruiter-one"
    text = "Power BI hiring"


def test_target_classification():
    assert classify_target("Senior Technical Recruiter") == "recruiter"
    assert classify_target("Talent Acquisition Partner") == "recruiter"
    assert classify_target("HR Business Partner") == "hr"
    assert classify_target("Hiring Manager, Analytics") == "hiring_manager"


def test_score_target_and_drafts(tmp_path):
    target = score_target(Person(), "Power BI Developer", "Example")
    assert target.target_type == "recruiter"
    assert target.profile_url.endswith("/recruiter-one")
    draft = draft_connection(target, "Power BI Developer", ["Power BI", "SQL"])
    assert draft["status"] == "drafted"
    follow = draft_followup(target, "Thanks for connecting.", path=None)
    assert follow["status"] == "drafted"
    assert follow["target"]["name"] == "Recruiter One"


def test_build_outreach_plan_links_people_to_job():
    plan = build_outreach_plan(
        [Person()],
        {"title": "Power BI Developer", "company": "Example", "url": "https://www.linkedin.com/jobs/view/1"},
    )
    assert len(plan) == 1
    assert plan[0].target_type == "recruiter"
    assert plan[0].job_url.endswith("/1")
