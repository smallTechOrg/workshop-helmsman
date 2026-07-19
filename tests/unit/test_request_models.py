import pytest
from pydantic import ValidationError

from src.helmsman.api.admin import MilestoneIn, WorkshopCreate
from src.helmsman.api.facilitator import AnswerBody
from src.helmsman.api.participant import HelpBody, JoinBody

VALID_MILESTONE = {"title": "Set up", "content_md": "x", "minutes": 30}


def test_workshop_name_is_trimmed():
    body = WorkshopCreate(name="  Lab  ", milestones=[VALID_MILESTONE])
    assert body.name == "Lab"


def test_workshop_name_empty_after_trim_rejected():
    with pytest.raises(ValidationError):
        WorkshopCreate(name="   ", milestones=[VALID_MILESTONE])


def test_workshop_name_over_120_rejected():
    with pytest.raises(ValidationError):
        WorkshopCreate(name="x" * 121, milestones=[VALID_MILESTONE])


def test_workshop_description_over_10000_rejected():
    with pytest.raises(ValidationError):
        WorkshopCreate(name="Lab", description_md="x" * 10_001, milestones=[VALID_MILESTONE])


def test_workshop_requires_at_least_one_milestone():
    with pytest.raises(ValidationError):
        WorkshopCreate(name="Lab", milestones=[])


def test_workshop_rejects_more_than_50_milestones():
    with pytest.raises(ValidationError):
        WorkshopCreate(name="Lab", milestones=[VALID_MILESTONE] * 51)


def test_milestone_title_bounds():
    with pytest.raises(ValidationError):
        MilestoneIn(title="")
    with pytest.raises(ValidationError):
        MilestoneIn(title="x" * 201)


def test_milestone_content_over_20000_rejected():
    with pytest.raises(ValidationError):
        MilestoneIn(title="ok", content_md="x" * 20_001)


def test_milestone_minutes_bounds():
    with pytest.raises(ValidationError):
        MilestoneIn(title="ok", minutes=0)
    with pytest.raises(ValidationError):
        MilestoneIn(title="ok", minutes=481)
    assert MilestoneIn(title="ok", minutes=None).minutes is None
    assert MilestoneIn(title="ok", minutes=480).minutes == 480


def test_join_name_trimmed_and_bounded():
    assert JoinBody(name="  Priya ").name == "Priya"
    with pytest.raises(ValidationError):
        JoinBody(name="   ")
    with pytest.raises(ValidationError):
        JoinBody(name="x" * 81)


def test_help_message_bounds():
    assert HelpBody(message="stuck").message == "stuck"
    with pytest.raises(ValidationError):
        HelpBody(message="")
    with pytest.raises(ValidationError):
        HelpBody(message="x" * 4001)


def test_answer_md_bounds():
    assert AnswerBody(answer_md="Check `.env`").answer_md == "Check `.env`"
    with pytest.raises(ValidationError):
        AnswerBody(answer_md="")
    with pytest.raises(ValidationError):
        AnswerBody(answer_md="x" * 10_001)
