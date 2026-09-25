from app.resume_match import match_resume_to_job
from app.resume_tailoring import tailor_resume


def test_resume_match_is_factual():
    report = match_resume_to_job("Power BI SQL DAX", "Power BI SQL", ["Power BI", "SQL", "DAX"])
    assert report.matched_skills == ["Power BI", "SQL"]
    assert report.missing_skills == ["DAX"]


def test_resume_tailoring_does_not_invent():
    result = tailor_resume("Power BI role", "Power BI", ["Power BI", "Snowflake"])
    assert result.relevant_skills == ["Power BI"]
    assert "Snowflake" in result.keyword_suggestions
