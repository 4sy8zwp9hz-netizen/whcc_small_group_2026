import json
from pathlib import Path
import re
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

from schedule import ROOT, create_app
from schedule.attendance import AttendanceStore, load_secret
from schedule.data import CHICAGO

NOW = datetime(2026, 10, 1, 12, tzinfo=CHICAGO)


class Source:
    def __init__(self):
        self.rows = [
            {"date": "2026-10-02", "time": "18:00", "topic": "A gathering"},
            {"date": "2026-10-09", "time": "18:00", "topic": "Another gathering"},
        ]
        self.fail = False

    def read(self):
        if self.fail:
            raise TimeoutError()
        return self.rows


def make_app(source=None, **config):
    return create_app({
        "TESTING": True, "DATA_SOURCE": "csv", "SHEET_LAYOUT": "table",
        "FIELD_MAPPING_JSON": "{}", "DATE_FORMAT": "%Y-%m-%d", "TIME_FORMAT": "%H:%M",
        "SECRET_KEY": "fictional-test-secret-not-used-outside-tests",
        **config,
    }, source=source or Source(), now=lambda: NOW)


def setup(client):
    html = client.get("/").get_data(as_text=True)
    with client.session_transaction() as session:
        csrf = session["csrf"]
        visitor = session["household_id"]
    key = re.search(r'data-meeting="([a-f0-9]+)"', html)[1]
    return key, csrf, visitor


def submit(client, key, csrf, action="all", **fields):
    return client.post("/attendance/" + key, data={
        "csrf": csrf, "action": action, "household": "Example family",
        "people": "Alex, Sam, Kai", **fields,
    }, headers={"Accept": "application/json"})


def test_first_response_selects_whole_household_then_can_exclude_one():
    app = make_app()
    client = app.test_client()
    key, csrf, visitor = setup(client)
    response = submit(client, key, csrf)
    assert response.status_code == 200
    store = app.extensions["attendance"].store
    members = store.household(visitor)["members"]
    assert store.summaries([key], visitor)[key]["people"] == 3
    selected = [members[0]["id"], members[1]["id"]]
    response = submit(client, key, csrf, "custom", attending=selected)
    assert response.status_code == 200
    summary = store.summaries([key], visitor)[key]
    assert summary["people"] == 2
    assert summary["going"][0]["names"] == ["Alex", "Sam"]
    assert "Saved. Tap a name" in response.json["panels"][key]


def test_cookie_remembers_household_and_current_response():
    app = make_app()
    client = app.test_client()
    key, csrf, visitor = setup(client)
    submit(client, key, csrf, "none")
    html = client.get("/").get_data(as_text=True)
    assert "Example family" in html
    assert 'name="household"' not in html
    assert 'value="none" class="rsvp-choice" aria-pressed="true"' in html
    with client.session_transaction() as session:
        assert session["household_id"] == visitor


def test_cookie_flags_and_no_names_in_session():
    client = make_app().test_client()
    response = client.get("/")
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Expires=" in cookie
    with client.session_transaction() as session:
        assert set(session) == {"household_id", "csrf", "_permanent"}
    secure = make_app(SESSION_COOKIE_SECURE=True).test_client().get("/")
    assert "Secure" in secure.headers["Set-Cookie"]


def test_repeat_taps_do_not_duplicate_people_or_households():
    app = make_app()
    client = app.test_client()
    key, csrf, visitor = setup(client)
    for _ in range(3):
        assert submit(client, key, csrf).status_code == 200
    summary = app.extensions["attendance"].store.summaries([key], visitor)[key]
    assert summary["people"] == 3 and len(summary["going"]) == 1


def test_separate_browsers_have_independent_households():
    app = make_app()
    first, second = app.test_client(), app.test_client()
    key, csrf, visitor = setup(first)
    key2, csrf2, visitor2 = setup(second)
    assert visitor != visitor2 and key == key2
    submit(first, key, csrf)
    submit(second, key, csrf2, household="Other family", people="Casey")
    store = app.extensions["attendance"].store
    assert store.summaries([key], visitor)[key]["people"] == 4
    submit(first, key, csrf, "none")
    summary = store.summaries([key], visitor2)[key]
    assert summary["people"] == 1 and summary["not_going"] == 1


@pytest.mark.parametrize("token", ["", "bad-token", "\u2603"])
def test_csrf_required_and_invalid_tokens_never_write(token):
    app = make_app()
    client = app.test_client()
    key, _, visitor = setup(client)
    assert submit(client, key, token).status_code == 400
    assert app.extensions["attendance"].store.household(visitor) is None


@pytest.mark.parametrize("fields", [
    {"people": ""}, {"people": "Alex, Alex"},
    {"people": ",".join("Person"+str(i) for i in range(21))},
    {"household": "a" * 61}, {"people": "a" * 41},
])
def test_profile_validation_does_not_leave_partial_records(fields):
    app = make_app()
    client = app.test_client()
    key, csrf, visitor = setup(client)
    assert submit(client, key, csrf, **fields).status_code == 400
    assert app.extensions["attendance"].store.household(visitor) is None


def test_invalid_member_cannot_be_added_to_household_response():
    app = make_app()
    client = app.test_client()
    key, csrf, visitor = setup(client)
    submit(client, key, csrf)
    assert submit(client, key, csrf, "custom", attending="foreign-member").status_code == 400
    assert app.extensions["attendance"].store.summaries([key], visitor)[key]["people"] == 3


def test_clear_keeps_profile_but_removes_response():
    app = make_app()
    client = app.test_client()
    key, csrf, visitor = setup(client)
    submit(client, key, csrf)
    assert submit(client, key, csrf, "clear").status_code == 200
    store = app.extensions["attendance"].store
    assert store.household(visitor)
    assert store.summaries([key], visitor)[key]["own"] is None
    assert store.summaries([key], visitor)[key]["people"] == 0


def test_forget_requires_csrf_and_does_not_delete_existing_response():
    app = make_app()
    client = app.test_client()
    key, csrf, visitor = setup(client)
    submit(client, key, csrf)
    assert client.post("/household/forget").status_code == 400
    assert client.post("/household/forget", data={"csrf": csrf}).status_code == 303
    _, _, new_visitor = setup(client)
    assert visitor != new_visitor
    store = app.extensions["attendance"].store
    assert store.household(new_visitor) is None
    assert store.summaries([key], visitor)[key]["people"] == 3


@pytest.mark.parametrize("change", ["cancel", "past", "duplicate", "stale", "missing"])
def test_changed_schedule_rejects_response(change):
    source = Source()
    app = make_app(source)
    client = app.test_client()
    key, csrf, visitor = setup(client)
    if change == "cancel":
        source.rows[0]["status"] = "canceled"
    elif change == "past":
        source.rows[0]["date"] = "2026-09-25"
    elif change == "duplicate":
        source.rows.append(dict(source.rows[0]))
    elif change == "stale":
        source.fail = True
    else:
        source.rows = source.rows[1:]
    app.extensions["schedule_cache"].retry_at = float("-inf")
    result = submit(client, key, csrf)
    assert result.status_code == (503 if change == "stale" else 409)
    assert app.extensions["attendance"].store.household(visitor) is None


def test_edited_topic_and_time_keep_same_meeting_key():
    source = Source()
    app = make_app(source)
    client = app.test_client()
    key, csrf, _ = setup(client)
    submit(client, key, csrf)
    source.rows[0].update(topic="Updated topic", time="19:30")
    app.extensions["schedule_cache"].retry_at = float("-inf")
    assert setup(client)[0] == key
    assert "3 people going" in client.get("/").get_data(as_text=True)


def test_source_namespace_isolated():
    first = make_app(CSV_PATH="data/sample.csv")
    second = make_app(CSV_PATH="private/another.csv")
    assert setup(first.test_client())[0] != setup(second.test_client())[0]


def test_profile_text_is_escaped():
    client = make_app().test_client()
    key, csrf, _ = setup(client)
    response = submit(client, key, csrf, household="<script>alert(1)</script>", people="Alex")
    panel = response.json["panels"][key]
    assert "<script>" not in panel and "&lt;script&gt;" in panel


def test_non_javascript_form_redirects_back_to_meeting():
    client = make_app().test_client()
    key, csrf, _ = setup(client)
    response = client.post("/attendance/" + key, data={
        "csrf": csrf, "action": "all", "household": "Example", "people": "Alex, Sam",
    })
    assert response.status_code == 303
    assert response.headers["Location"] == "/#meeting-" + key


def test_week_card_precedes_navigation_without_duplicate():
    client = make_app().test_client()
    key, _, _ = setup(client)
    html = client.get("/").get_data(as_text=True)
    assert html.index('class="meeting featured') < html.index('<nav')
    assert "This week" in html
    assert html.count('id="meeting-' + key + '"') == 1
    assert "A place to gather" not in html


def test_current_week_off_entry_still_featured():
    source = Source()
    source.rows[0]["status"] = "canceled"
    html = make_app(source).test_client().get("/").get_data(as_text=True)
    featured = html.split('<article class="meeting featured')[1].split("</article>")[0]
    assert "This week" in featured and "Canceled" in featured
    assert "rsvp-form" not in featured
    assert "Another gathering" in html


def test_database_and_secret_survive_restart():
    cache_dir = (ROOT / ".cache").resolve()
    cache_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="attendance-test-", dir=cache_dir) as folder:
        path = Path(folder)
        assert path.resolve().parent == cache_dir
        secret = load_secret(path / "session.key")
        first = AttendanceStore(path / "responses.sqlite3")
        first.save("visitor", "meeting", "all", "Example", "Alex, Sam", [], NOW.isoformat())
        first.connection.close()
        second = AttendanceStore(path / "responses.sqlite3")
        try:
            assert load_secret(path / "session.key") == secret
            assert second.summaries(["meeting"], "visitor")["meeting"]["people"] == 2
        finally:
            second.connection.close()


def test_storage_failure_does_not_report_saved():
    client = make_app().test_client()
    key, csrf, _ = setup(client)
    import sqlite3
    with patch.object(AttendanceStore, "save", side_effect=sqlite3.OperationalError):
        response = submit(client, key, csrf)
    assert response.status_code == 503
    assert "could not be saved" in response.json["error"]
