from app.story_bank import Story, StoryBank


def test_story_bank_round_trip(tmp_path):
    bank = StoryBank(tmp_path / "stories.sqlite3")
    created = bank.add(Story(
        title="Power BI automation",
        situation="Manual reporting",
        action="Built an automated dashboard workflow",
        result="Reduced manual work",
        metric="30%",
        lesson="Automate repeatable reporting first",
        tags="powerbi,automation",
    ))
    assert created.story_id
    rows = bank.list()
    assert rows[0].title == "Power BI automation"
    found = bank.search("30%")
    assert found[0].metric == "30%"
