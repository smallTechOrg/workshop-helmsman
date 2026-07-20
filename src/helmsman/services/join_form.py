"""Custom join-form fields: definition validation + answer validation.

Shapes per spec/data-model.md §JSON shapes:
  field def: {"key","type" ("text"|"dropdown"),"label","required",("options")}
  answers:   {field_key: value}
"""

from __future__ import annotations

import json
import re

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
FIELDS_MAX = 12
LABEL_MAX = 120
OPTIONS_MAX = 24
OPTION_LABEL_MAX = 120
TEXT_ANSWER_MAX = 500


class JoinFormError(ValueError):
    """Raised with a participant/facilitator-friendly message."""


def validate_field_defs(raw: object) -> list[dict]:
    """Validate a join-form definition; returns the normalized list."""
    if not isinstance(raw, list):
        raise JoinFormError("join_form must be a list of fields")
    if len(raw) > FIELDS_MAX:
        raise JoinFormError(f"join_form supports at most {FIELDS_MAX} fields")
    normalized: list[dict] = []
    seen_keys: set[str] = set()
    for i, field in enumerate(raw):
        if not isinstance(field, dict):
            raise JoinFormError(f"field #{i + 1} must be an object")
        key = field.get("key")
        if not isinstance(key, str) or not KEY_RE.match(key):
            raise JoinFormError(
                f"field #{i + 1}: key must match {KEY_RE.pattern}"
            )
        if key in seen_keys:
            raise JoinFormError(f"duplicate field key '{key}'")
        seen_keys.add(key)
        ftype = field.get("type")
        if ftype not in ("text", "dropdown"):
            raise JoinFormError(f"field '{key}': type must be 'text' or 'dropdown'")
        label = field.get("label")
        if not isinstance(label, str) or not (1 <= len(label.strip()) <= LABEL_MAX):
            raise JoinFormError(f"field '{key}': label must be 1–{LABEL_MAX} characters")
        required = field.get("required", False)
        if not isinstance(required, bool):
            raise JoinFormError(f"field '{key}': required must be true or false")
        entry: dict = {"key": key, "type": ftype, "label": label.strip(), "required": required}
        if ftype == "dropdown":
            options = field.get("options")
            if (
                not isinstance(options, list)
                or not (1 <= len(options) <= OPTIONS_MAX)
                or not all(
                    isinstance(o, str) and 1 <= len(o.strip()) <= OPTION_LABEL_MAX
                    for o in options
                )
            ):
                raise JoinFormError(
                    f"field '{key}': dropdown needs 1–{OPTIONS_MAX} non-empty options"
                )
            entry["options"] = [o.strip() for o in options]
        normalized.append(entry)
    return normalized


def validate_answers(
    join_form_json: str, raw_answers: object, *, require_all: bool = True
) -> dict[str, str]:
    """Validate participant answers against the workshop's join form.

    Returns the normalized {key: value} dict (unknown keys dropped). With
    ``require_all=False`` a blank required field is allowed to stay blank —
    used when a facilitator edits an existing participant and shouldn't be
    forced to fill fields that became required after the participant joined.
    """
    fields = json.loads(join_form_json or "[]")
    answers = raw_answers if isinstance(raw_answers, dict) else {}
    normalized: dict[str, str] = {}
    for field in fields:
        key, label = field["key"], field["label"]
        value = answers.get(key)
        value = value.strip() if isinstance(value, str) else ""
        if not value:
            if field.get("required") and require_all:
                raise JoinFormError(f"'{label}' is required")
            continue
        if len(value) > TEXT_ANSWER_MAX:
            raise JoinFormError(f"'{label}' must be at most {TEXT_ANSWER_MAX} characters")
        if field["type"] == "dropdown" and value not in field.get("options", []):
            raise JoinFormError(f"'{label}' must be one of the listed options")
        normalized[key] = value
    return normalized
