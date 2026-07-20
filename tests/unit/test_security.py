from src.helmsman.security import (
    admin_key_matches,
    generate_admin_token,
    generate_join_slug,
    generate_participant_token,
)


def test_admin_token_is_43_chars_and_unique():
    tokens = {generate_admin_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) == 43 for t in tokens)


def test_participant_token_is_22_chars():
    assert len(generate_participant_token()) == 22


def test_join_slug_is_8_chars():
    assert len(generate_join_slug()) == 8


def test_tokens_are_url_safe():
    token = generate_admin_token()
    assert all(c.isalnum() or c in "-_" for c in token)


def test_admin_key_matches_equal():
    assert admin_key_matches("sekrit-key", "sekrit-key") is True


def test_admin_key_matches_rejects_wrong_key():
    assert admin_key_matches("wrong", "sekrit-key") is False


def test_admin_key_matches_rejects_missing_key():
    assert admin_key_matches(None, "sekrit-key") is False


def test_admin_key_matches_rejects_empty_expected():
    assert admin_key_matches("anything", "") is False
