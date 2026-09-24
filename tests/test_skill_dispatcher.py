import pytest
from app.skill_dispatcher import dispatch

def test_dispatch_content_skills():
    assert dispatch("hook_extractor", text="3 lessons\nbody")["hook"] == "3 lessons"
    assert dispatch("post_writer", topic="Power BI", angle="Refresh optimization").kind == "post"

def test_dispatch_rejects_unknown():
    with pytest.raises(ValueError):
        dispatch("does_not_exist")
