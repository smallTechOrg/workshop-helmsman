def test_get_join_page_shows_workshop_and_counts(client, workshop):
    data = client.get(f"/api/join/{workshop['join_slug']}").json()["data"]
    assert data["workshop"]["name"] == workshop["name"]
    assert data["workshop"]["description_md"] == workshop["description_md"]
    assert data["workshop"]["status"] == "live"
    assert data["workshop"]["milestone_count"] == 3
    assert data["workshop"]["participant_count"] == 0
    assert data["me"] is None


def test_join_sets_cookie_with_exact_attributes(make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    assert len(joined["participant_token"]) == 22
    assert joined["name"] == "Priya"
    assert joined["participant_url"] == f"http://testserver/p/{joined['participant_token']}"

    cookie_name = f"helmsman_p_{workshop['id']}"
    assert browser.cookies.get(cookie_name) == joined["participant_token"]


def test_join_cookie_header_attributes(make_client, workshop):
    browser = make_client()
    response = browser.post(f"/api/join/{workshop['join_slug']}", json={"name": "Priya"})
    set_cookie = response.headers["set-cookie"].lower()
    assert f"helmsman_p_{workshop['id']}=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/" in set_cookie
    assert "max-age=2592000" in set_cookie


def test_cookie_auto_resume_returns_me(make_client, workshop, join_participant):
    browser = make_client()
    joined = join_participant(browser, workshop["join_slug"], "Priya")
    data = browser.get(f"/api/join/{workshop['join_slug']}").json()["data"]
    assert data["me"] == {"participant_token": joined["participant_token"], "name": "Priya"}
    assert data["workshop"]["participant_count"] == 1


def test_join_page_without_cookie_has_no_me(make_client, workshop, join_participant):
    join_participant(make_client(), workshop["join_slug"], "Priya")
    fresh_browser = make_client()
    data = fresh_browser.get(f"/api/join/{workshop['join_slug']}").json()["data"]
    assert data["me"] is None


def test_stale_cookie_for_unknown_participant_is_ignored(make_client, workshop):
    browser = make_client()
    browser.cookies.set(f"helmsman_p_{workshop['id']}", "not-a-real-token")
    data = browser.get(f"/api/join/{workshop['join_slug']}").json()["data"]
    assert data["me"] is None


def test_personal_link_works_cross_device_without_cookie(
    make_client, workshop, join_participant
):
    phone = make_client()
    joined = join_participant(phone, workshop["join_slug"], "Priya")
    laptop = make_client()  # no cookies at all
    state = laptop.get(f"/api/p/{joined['participant_token']}/state").json()["data"]
    assert state["changed"] is True
    assert state["me"]["name"] == "Priya"


def test_duplicate_names_are_allowed(make_client, workshop, join_participant):
    first = join_participant(make_client(), workshop["join_slug"], "Priya")
    second = join_participant(make_client(), workshop["join_slug"], "Priya")
    assert first["participant_token"] != second["participant_token"]
