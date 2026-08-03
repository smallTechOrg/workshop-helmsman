"""creator_email normalization/validation + log masking (spec/api.md §Phase 6)."""

import pytest
from pydantic import ValidationError

from src.helmsman.services.workshops import (
    PublicWorkshopCreate,
    mask_email,
    normalize_creator_email,
)

VALID_MILESTONE = {"title": "Set up", "content_md": "x", "minutes": 30}


def test_email_is_trimmed_and_lowercased():
    assert normalize_creator_email("  Asha@Example.COM ") == "asha@example.com"


@pytest.mark.parametrize(
    "value",
    [None, "", "   ", "a@b", "no-at.example.com", "two@@example.com", "a b@example.com", "a@b c.com"],
)
def test_malformed_emails_rejected(value):
    with pytest.raises(ValueError):
        normalize_creator_email(value)


def test_email_over_254_chars_rejected():
    with pytest.raises(ValueError):
        normalize_creator_email("x" * 250 + "@example.com")


def test_email_at_max_length_accepted():
    local = "x" * (254 - len("@example.com"))
    assert normalize_creator_email(f"{local}@example.com").endswith("@example.com")


def test_mask_email_keeps_two_chars_and_domain():
    assert mask_email("asha@example.com") == "as***@example.com"


def test_public_body_requires_email():
    with pytest.raises(ValidationError):
        PublicWorkshopCreate(name="Lab", milestones=[VALID_MILESTONE])


def test_public_body_normalizes_email_and_keeps_admin_validation():
    body = PublicWorkshopCreate(
        name="  Lab  ", milestones=[VALID_MILESTONE], creator_email=" Asha@Example.com "
    )
    assert body.creator_email == "asha@example.com"
    assert body.name == "Lab"

    with pytest.raises(ValidationError):
        PublicWorkshopCreate(name="   ", milestones=[VALID_MILESTONE], creator_email="a@b.com")
