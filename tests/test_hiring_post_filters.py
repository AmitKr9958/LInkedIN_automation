from app.daily_agent import _rank_hiring_posts


def test_hiring_post_requires_target_city_even_when_remote():
    posts = [{
        "author": "Remote Recruiter",
        "text": "We are hiring a Senior Power BI Developer. Fully remote across India.",
        "profile_url": "https://linkedin.test/in/remote",
    }]
    assert _rank_hiring_posts(
        posts, locations=["Delhi", "Gurgaon", "Noida"], keywords=["Power BI Developer"]
    ) == []


def test_hiring_post_excludes_fresher_role():
    posts = [{
        "author": "Recruiter",
        "text": "We are hiring Data Analyst freshers in Gurgaon. Apply now!",
        "profile_url": "https://linkedin.test/in/recruiter",
    }]
    assert _rank_hiring_posts(
        posts, locations=["Delhi", "Gurgaon", "Noida"], keywords=["Data Analyst"]
    ) == []


def test_hiring_post_accepts_target_city_and_role():
    posts = [{
        "author": "Hiring Manager",
        "text": "We are hiring a Power BI Developer in Gurgaon. Apply now!",
        "profile_url": "https://linkedin.test/in/hiring-manager",
    }]
    ranked = _rank_hiring_posts(
        posts, locations=["Delhi", "Gurgaon", "Noida"], keywords=["Power BI Developer"]
    )
    assert len(ranked) == 1
    assert ranked[0]["post"]["author"] == "Hiring Manager"
