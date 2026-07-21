"""Per-milestone completion inputs.

A milestone can optionally require the participant to submit a value before they
may mark it complete — a GitHub repo URL, a generic URL, a free-text answer, or
a choice from a dropdown. The config is stored on the milestone as JSON
(``milestone.input_config_json``); the submitted value is stored on the
completion (``milestone_completion.input_value``).

Both the config definition (facilitator side) and the submitted value
(participant side) are validated here so the two surfaces never disagree.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

INPUT_TYPES = ("github_url", "url", "text", "dropdown")
LABEL_MAX = 120
VALUE_MAX = 500
OPTIONS_MAX = 20

# What the participant sees as the field's default prompt when no label is set.
_DEFAULT_LABELS = {
    "github_url": "GitHub URL",
    "url": "Link (URL)",
    "text": "Your answer",
    "dropdown": "Choose an option",
}


class MilestoneInputError(ValueError):
    """Raised for an invalid input config or an invalid submitted value."""


def validate_input_config(raw: object) -> dict | None:
    """Validate a facilitator-supplied input config.

    ``None`` / empty ⇒ the milestone has no required input. Returns a normalized
    dict otherwise. Raises :class:`MilestoneInputError` on a malformed config.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise MilestoneInputError("input config must be an object")

    type_ = raw.get("type")
    if type_ not in INPUT_TYPES:
        raise MilestoneInputError(
            f"input type must be one of: {', '.join(INPUT_TYPES)}"
        )

    label = str(raw.get("label") or "").strip() or _DEFAULT_LABELS[type_]
    if len(label) > LABEL_MAX:
        raise MilestoneInputError(f"input label must be at most {LABEL_MAX} characters")

    config: dict = {"type": type_, "label": label}

    if type_ == "dropdown":
        options_raw = raw.get("options")
        if not isinstance(options_raw, list):
            raise MilestoneInputError("a dropdown input needs an options list")
        options = [str(o).strip() for o in options_raw if str(o).strip()]
        if not options:
            raise MilestoneInputError("a dropdown input needs at least one option")
        if len(options) > OPTIONS_MAX:
            raise MilestoneInputError(f"a dropdown can have at most {OPTIONS_MAX} options")
        if len(set(options)) != len(options):
            raise MilestoneInputError("dropdown options must be unique")
        config["options"] = options

    return config


def load_input_config(input_config_json: str | None) -> dict | None:
    """Parse a stored config; tolerant of null/empty."""
    if not input_config_json:
        return None
    try:
        return json.loads(input_config_json)
    except (ValueError, TypeError):
        return None


def _looks_like_url(value: str) -> object:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return parsed


def validate_input_value(config: dict, raw_value: object) -> str:
    """Validate a participant's submitted value against ``config``.

    Returns the normalized (trimmed) value. Raises :class:`MilestoneInputError`
    with a friendly, participant-facing message on failure.
    """
    value = "" if raw_value is None else str(raw_value).strip()
    label = config.get("label") or "This field"
    type_ = config.get("type")

    if not value:
        raise MilestoneInputError(f"{label} is required to complete this milestone.")
    if len(value) > VALUE_MAX:
        raise MilestoneInputError(f"{label} must be at most {VALUE_MAX} characters.")

    if type_ == "github_url":
        parsed = _looks_like_url(value)
        if parsed is None:
            raise MilestoneInputError("Enter a valid URL (starting with http:// or https://).")
        host = parsed.netloc.lower().split("@")[-1].split(":")[0]
        if host != "github.com" and not host.endswith(".github.com"):
            raise MilestoneInputError("Enter a GitHub URL (a link on github.com).")
    elif type_ == "url":
        if _looks_like_url(value) is None:
            raise MilestoneInputError("Enter a valid URL (starting with http:// or https://).")
    elif type_ == "dropdown":
        options = config.get("options") or []
        if value not in options:
            raise MilestoneInputError(f"Choose one of: {', '.join(options)}.")
    # "text" — any non-empty value within length bounds is fine.

    return value
