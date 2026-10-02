"""Fictional admin roster, member selection and durable attendance contracts."""
import copy
import re
from unittest.mock import patch

from test_backend_admin import login, make
from test_cloud_run import seed, GROUP, HASH, group_login


def form(client, household="", meeting="", **updates):
    response = client.get("/admin/households", query_string={"household_id": household, "meeting_id": meeting})
    token = re.search(r'name="token" value="([^"]+)"', response.text).group(1)
    with client.session_transaction() as session:
        csrf = session["csrf"]
    return {"csrf": csrf, "token": token, "household_id": household, "meeting_id": meeting,
            "name": "Fictional family", "new_people": "Alex, Sam", "action": "profile", **updates}


def create(client, key="", action="profile"):
    return client.post("/admin/households", data=form(client, meeting=key, action=action))


def identity(publisher):
    return publisher.remote[0]["households"][0]["id"]


def test_group_admin_and_csrf_required():
    app, _, _ = make(GROUP_ACCESS_PASSWORD_HASH=HASH)
    client = app.test_client()
    assert client.get("/admin/households").location.endswith("/group/login")
    group_login(client)
    assert client.get("/admin/households").location.endswith("/admin/login")
    login(client)
    assert client.post("/admin/households", data={"csrf": "bad"}).status_code == 400


def test_roster_creation_member_selection_clear_and_cold_recovery():
    app, source, backend, publisher = seed()
    client = app.test_client()
    login(client)
    key = backend.cache.get().meetings[0].record_id
    assert create(client, key, "all").status_code == 303
    hid = identity(publisher)
    people = copy.deepcopy(publisher.remote[0]["households"][0]["members"])
    assert len(publisher.remote[0]["responses"][0]["attending"]) == 2
    for action, attending in [("custom", [people[0]["id"]]), ("none", []), ("clear", None)]:
        data = form(client, hid, key, action=action, new_people="",
                    **{"member_" + p["id"]: p["name"] for p in people})
        data["attending"] = people[0]["id"]
        assert client.post("/admin/households", data=data).status_code == 303
        replies = publisher.remote[0]["responses"]
        assert (replies[0]["attending"] if replies else None) == attending
    app2, _, backend2 = make(source=source)
    backend2.publisher, backend2.strict = publisher, True
    backend2.cache.get()
    assert backend2.export()[0]["households"] == publisher.remote[0]["households"]


def test_profile_rename_and_add_preserve_ids_history_and_member_cookie():
    app, _, backend, publisher = seed()
    client = app.test_client()
    login(client)
    key = backend.cache.get().meetings[0].record_id
    create(client, key, "all")
    hid = identity(publisher)
    people = publisher.remote[0]["households"][0]["members"]
    data = form(client, hid, key, new_people="Taylor",
                **{"member_" + p["id"]: p["name"] + " renamed" for p in people})
    assert client.post("/admin/households", data=data).status_code == 303
    updated = publisher.remote[0]["households"][0]
    assert [p["id"] for p in updated["members"][:2]] == [p["id"] for p in people]
    assert publisher.remote[0]["responses"][0]["attending"] == [p["id"] for p in people]
    member = app.test_client()
    member.get("/")
    with member.session_transaction() as session:
        csrf = session["csrf"]
    before = copy.deepcopy(publisher.remote)
    assert member.post("/household/select", data={"csrf": csrf, "household_id": hid}).status_code == 303
    assert publisher.remote == before  # Claiming a roster never submits attendance.
    assert "renamed" in member.get("/").text
    with member.session_transaction() as session:
        visitor = session["household_id"]
    assert app.extensions["attendance"].store.household(visitor)["members"] == updated["members"]


def test_stale_admin_form_and_unknown_household_cannot_overwrite():
    app, _, backend, publisher = seed()
    client = app.test_client()
    login(client)
    key = backend.cache.get().meetings[0].record_id
    create(client, key, "all")
    hid = identity(publisher)
    people = publisher.remote[0]["households"][0]["members"]
    data = form(client, hid, key, action="none", new_people="",
                **{"member_" + p["id"]: p["name"] for p in people})
    publisher.remote[0]["responses"][0]["attending"] = []
    publisher.remote[0]["responses"][0]["updated_at"] = "2026-10-01T13:00:00-05:00"
    before = copy.deepcopy(publisher.remote)
    assert client.post("/admin/households", data=data).status_code == 409
    assert publisher.remote == before
    bad = form(client, "f" * 64, key)
    assert client.post("/admin/households", data=bad).status_code == 409


def test_failed_write_rolls_back_profile_and_response():
    app, _, backend, publisher = seed()
    client = app.test_client()
    login(client)
    key = backend.cache.get().meetings[0].record_id
    data = form(client, meeting=key, action="all")
    with patch.object(publisher, "write", side_effect=TimeoutError):
        result = client.post("/admin/households", data=data)
    assert result.status_code == 409 and "not confirmed" in result.text
    assert not backend.export()[0]["households"] and not backend.export()[0]["responses"]


def test_guest_can_enter_only_own_name_and_choose_own_roster_later():
    app, _, backend, publisher = seed()
    guest = app.test_client()
    guest.get("/")
    with guest.session_transaction() as session:
        csrf = session["csrf"]
    key = backend.records()[0]["id"]
    assert guest.post("/attendance/" + key, data={"csrf": csrf, "action": "all", "people": "Visitor"}).status_code == 303
    assert publisher.remote[0]["households"][0]["name"] == "Visitor household"
    another = app.test_client()
    assert "Choose your household" in another.get("/").text
    with another.session_transaction() as session:
        csrf = session["csrf"]
    assert another.post("/household/select", data={"csrf": "bad", "household_id": identity(publisher)}).status_code == 400
    assert another.post("/household/select", data={"csrf": csrf, "household_id": "unknown"}).status_code == 404


def test_outage_support_and_closed_meeting_rejection():
    app, source, backend, publisher = seed()
    source.fail = True
    client = app.test_client()
    login(client)
    key = backend.cache.get().meetings[0].record_id
    assert create(client, key, "all").status_code == 303
    hid = identity(publisher)
    people = publisher.remote[0]["households"][0]["members"]
    data = form(client, hid, key, action="all", new_people="",
                **{"member_" + p["id"]: p["name"] for p in people})
    publisher.remote[0]["record"]["values"]["status"] = "canceled"
    assert client.post("/admin/households", data=data).status_code == 409
    data = form(client, hid, key, action="none", new_people="",
                **{"member_" + p["id"]: p["name"] for p in people})
    assert client.post("/admin/households", data=data).status_code == 409

def test_two_admin_writers_keep_unrelated_updates_and_reject_same_profile_changes():
    from test_review_fixes import Transport
    app, source, backend, publisher = seed()
    transport = Transport(publisher.remote)
    backend.publisher = transport.adapter()
    app2, _, backend2 = make(source=source)
    backend2.publisher, backend2.strict = transport.adapter(), True
    first, second = app.test_client(), app2.test_client()
    login(first)
    login(second)
    key = backend.records()[0]["id"]
    create(first, key, "all")
    remote = backend.publisher.read()
    hid = remote[0]["households"][0]["id"]
    people = remote[0]["households"][0]["members"]
    fields = {"member_" + p["id"]: p["name"] for p in people}
    stale = form(second, hid, key, action="none", new_people="", **fields)
    change = form(first, hid, key, name="Corrected fictional family", new_people="", **fields)
    assert first.post("/admin/households", data=change).status_code == 303
    assert second.post("/admin/households", data=stale).status_code == 409
    assert backend2.publisher.read()[0]["households"][0]["name"] == "Corrected fictional family"
    # A fresh form sees and preserves the other writer's correction.
    fresh = form(second, hid, key, name="Corrected fictional family", action="none", new_people="", **fields)
    assert second.post("/admin/households", data=fresh).status_code == 303
    assert backend.publisher.read()[0]["responses"][0]["attending"] == []
    import json
    event = json.loads(transport.posts[-1][16])
    assert not event["patch"]["records"] and not event["patch"]["profiles"]
    assert len(event["patch"]["responses"]) == 1


def test_existing_browser_profile_token_survives_restore_to_import_identity():
    app, _, backend, publisher = seed()
    member = app.test_client()
    member.get("/")
    with member.session_transaction() as session:
        csrf = session["csrf"]
    key = backend.records()[0]["id"]
    member.post("/attendance/" + key, data={"csrf": csrf, "action": "all", "people": "Alex, Sam"})
    admin = app.test_client()
    login(admin)
    hid = identity(publisher)
    people = publisher.remote[0]["households"][0]["members"]
    data = form(admin, hid, key, action="none", new_people="",
                **{"member_" + p["id"]: p["name"] for p in people})
    assert admin.post("/admin/households", data=data).status_code == 303


def test_invalid_roster_leaves_no_partial_data():
    app, _, backend, publisher = seed()
    client = app.test_client()
    login(client)
    for names in ["Alex, Alex", ",".join("Person" + str(i) for i in range(21)), "A" * 41]:
        assert client.post("/admin/households", data=form(client, new_people=names)).status_code == 400
        assert not backend.export()[0]["households"]



def test_back_preserves_saved_household_responses_and_authorization():
    app, _, backend, publisher = seed(GROUP_ACCESS_PASSWORD_HASH=HASH)
    client = app.test_client()
    group_login(client)
    csrf = login(client)
    key = backend.cache.get().meetings[0].record_id
    assert client.post('/attendance/' + key, data={'csrf': csrf, 'action': 'all', 'people': 'Alex, Sam'}).status_code == 303
    before = copy.deepcopy(publisher.remote)
    with client.session_transaction() as session:
        authorization = {k: v for k, v in session.items() if k != 'household_id'}
        old_identity = session['household_id']
    assert client.post('/household/back', data={'csrf': 'bad'}).status_code == 400
    with client.session_transaction() as session:
        assert session['household_id'] == old_identity
    assert client.post('/household/back', data={'csrf': csrf}).status_code == 303
    assert publisher.remote == before
    with client.session_transaction() as session:
        assert session['household_id'] != old_identity
        assert {k: v for k, v in session.items() if k != 'household_id'} == authorization
    assert client.get('/admin').status_code == 200
    page = client.get('/').text
    assert 'Choose your household' in page
    assert '<details class="guest-setup">' in page and '<details class="guest-setup" open' not in page
    assert app.extensions['attendance'].store.household(old_identity) is not None
    assert client.post('/household/select', data={'csrf': csrf, 'household_id': identity(publisher)}).status_code == 303
    assert 'Back to household selection' in client.get('/').text



def test_back_does_not_reset_browser_admin_login_throttle():
    app, _, _, _ = seed()
    client = app.test_client()
    csrf = login(client)
    for _ in range(10):
        assert client.post('/admin/login', data={'csrf': csrf, 'password': 'wrong'}).status_code == 401
    assert client.post('/household/back', data={'csrf': csrf}).status_code == 303
    assert client.post('/admin/login', data={'csrf': csrf, 'password': 'wrong'}).status_code == 429



def test_guest_submit_marks_all_entered_people_going_and_restores_member_controls():
    app, _, backend, publisher = seed()
    client = app.test_client()
    page = client.get('/').text
    assert '<button name="action" value="all" class="rsvp-choice">Submit</button>' in page
    assert 'All going' not in page and 'Not going' not in page
    with client.session_transaction() as session:
        csrf = session['csrf']
    key = backend.records()[0]['id']
    response = client.post('/attendance/' + key, data={'csrf': csrf, 'action': 'all', 'people': 'Visitor, Friend'})
    assert response.status_code == 303
    assert len(publisher.remote[0]['responses'][0]['attending']) == 2
    page = client.get('/').text
    assert 'All going' in page and 'Not going' in page
    assert '>Submit</button>' not in page



def test_later_meeting_plans_are_separate_from_this_weeks_response():
    from test_backend_admin import Source
    source = Source()
    source.rows += [{'date': '2026-10-09', 'time': '18:00', 'topic': 'Later fictional gathering'},
                    {'date': '2026-10-16', 'time': '18:00', 'topic': 'Canceled gathering', 'status': 'canceled'}]
    app, _, backend, publisher = seed(source=source)
    client = app.test_client()
    page = client.get('/').text
    assert page.count('<details class="planned-attendance">') == 1
    assert 'Can you make it?' in page
    with client.session_transaction() as session:
        csrf = session['csrf']
    later = next(r['id'] for r in backend.records() if r['values']['date'] == '2026-10-09')
    assert client.post('/attendance/' + later, data={'csrf': csrf, 'action': 'all', 'people': 'Visitor, Friend'}).status_code == 303
    replies = {i['record']['values']['date']: i['responses'] for i in publisher.remote}
    assert not replies['2026-10-02'] and not replies['2026-10-16']
    assert len(replies['2026-10-09'][0]['attending']) == 2
    page = client.get('/').text
    assert 'Can you make it?' in page and 'All going' in page
