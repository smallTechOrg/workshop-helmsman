from src.helmsman.observability.logging import mask_path, mask_token


def test_mask_token_shows_first_six_chars_only():
    assert mask_token("abcdefghij") == "abcdef…"


def test_mask_token_leaves_short_values_alone():
    assert mask_token("abc") == "abc"


def test_masks_facilitator_api_path():
    assert (
        mask_path("/api/f/AbCdEfGhIjKlMnOp/dashboard")
        == "/api/f/AbCdEf…/dashboard"
    )


def test_masks_participant_api_path():
    assert mask_path("/api/p/tok123456789/state") == "/api/p/tok123…/state"


def test_masks_pretty_participant_link():
    assert mask_path("/p/tok123456789") == "/p/tok123…"


def test_masks_pretty_facilitator_link():
    assert mask_path("/f/AbCdEfGhIj") == "/f/AbCdEf…"


def test_leaves_non_token_paths_alone():
    assert mask_path("/api/health") == "/api/health"
    assert mask_path("/api/admin/workshops") == "/api/admin/workshops"
    assert mask_path("/api/join/Ab3dEfGh") == "/api/join/Ab3dEfGh"
