import copy
import hashlib
import json
import tempfile
from pathlib import Path
from datetime import datetime

import pytest
from werkzeug.security import generate_password_hash

from schedule import ROOT, create_app
from schedule.backend import DataError, digest
from schedule.data import CHICAGO
from schedule.sheet_backend import HEADERS, SheetBackend

NOW = datetime(2026, 10, 1, 12, tzinfo=CHICAGO)
PASSWORD = "fictional-admin-password"
PASSWORD_HASH = generate_password_hash(PASSWORD, method="pbkdf2:sha256:1000")


class Source:
    def __init__(self):
        self.rows = [{"date": "2026-10-02", "time": "18:00", "topic": "Fictional gathering",
                      "host": "Alex", "notes": "Original note"}]
        self.fail = False

    def read(self):
        if self.fail:
            raise TimeoutError()
        return copy.deepcopy(self.rows)


class Publisher:
    def __init__(self, remote=None):
        self.remote = remote
        self.fail = False
        self.lose_ack = False
        self.writes = 0

    def read(self):
        if self.fail:
            raise TimeoutError()
        return copy.deepcopy(self.remote)

    def validate(self, items):
        SheetBackend.validate(items)

    def create(self, items):
        if self.remote is not None:
            raise DataError("Already exists")
        self.remote = copy.deepcopy(items)
        return 123

    def write(self, items):
        self.writes += 1
        self.remote = copy.deepcopy(items)
        if self.lose_ack:
            self.lose_ack = False
            raise TimeoutError()


def make(source=None, **config):
    source = source or Source()
    app = create_app({"TESTING": True, "SCHEDULE_EDITING": True, "BACKEND_SHEET_ENABLED": False,
                      "DATA_SOURCE": "csv", "SHEET_LAYOUT": "table", "FIELD_MAPPING_JSON": "{}",
                      "SECRET_KEY": "fictional-session-key", "ADMIN_PASSWORD_HASH": PASSWORD_HASH,
                      **config}, source=source, now=lambda: NOW)
    return app, source, app.extensions["backend"]


def login(client):
    client.get("/admin/login")
    with client.session_transaction() as session:
        csrf = session["csrf"]
    response = client.post("/admin/login", data={"csrf": csrf, "password": PASSWORD})
    assert response.status_code == 303
    with client.session_transaction() as session:
        return session["csrf"]


def refresh(backend):
    backend.invalidate()
    return backend.cache.get()


def form(record, csrf, **updates):
    return {"csrf": csrf, "revision": str(record["revision"]),
            **record["values"], "special_event": "false", **updates}


def test_admin_requires_login_and_csrf_and_can_edit():
    app, source, backend = make()
    client = app.test_client()
    assert client.get("/admin").status_code == 302
    assert client.post("/admin/login", data={"password": PASSWORD}).status_code == 400
    csrf = login(client)
    assert client.get("/admin").status_code == 200
    record = backend.records()[0]
    url = "/admin/meetings/" + record["id"]
    assert client.get(url).status_code == 200
    assert client.post(url, data=form(record, "bad")).status_code == 400
    assert client.post(url, data=form(record, csrf, topic="New app topic")).status_code == 303
    assert "New app topic" in client.get("/").text
    assert source.rows[0]["topic"] == "Fictional gathering"
    assert client.post("/admin/logout", data={"csrf": csrf}).status_code == 303
    assert client.get("/admin").status_code == 302


def test_bad_password_expiry_rotation_and_throttle():
    app, _, _ = make()
    client = app.test_client()
    csrf = login(client)
    with client.session_transaction() as session:
        session["admin_until"] = 0
    assert client.get("/admin").status_code == 302
    csrf = login(client)
    app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("another-fictional-password", method="pbkdf2:sha256:1000")
    assert client.get("/admin").status_code == 302
    for _ in range(8):
        assert client.post("/admin/login", data={"csrf": csrf, "password": "wrong"}).status_code == 401
    assert client.post("/admin/login", data={"csrf": csrf, "password": "wrong"}).status_code == 429


def test_field_merge_retains_override_and_flags_same_field_conflict():
    app, source, backend = make()
    refresh(backend)
    original = backend.records()[0]
    values = dict(original["values"], topic="App topic")
    backend.edit(original["id"], original["revision"], values, {})
    source.rows[0]["host"] = "Sam"
    refresh(backend)
    record = backend.records()[0]
    assert record["values"]["topic"] == "App topic" and record["values"]["host"] == "Sam"
    assert not record["conflicts"]
    source.rows[0]["topic"] = "Calendar topic"
    snapshot = refresh(backend)
    record = backend.records()[0]
    assert record["conflicts"] == {"topic": "Calendar topic"}
    assert snapshot.meetings[0].date_conflict
    assert not app.extensions["attendance"].allowed(snapshot.meetings[0], snapshot)
    before = copy.deepcopy(record)
    refresh(backend)
    assert backend.records()[0] == before
    with pytest.raises(DataError):
        backend.edit(record["id"], record["revision"], record["values"].copy(), {})
    backend.edit(record["id"], record["revision"], record["values"].copy(), {"topic": "calendar"})
    assert backend.records()[0]["values"]["topic"] == "Calendar topic"
    assert not backend.records()[0]["conflicts"]


def test_keep_app_conflict_choice_survives_later_refresh():
    _, source, backend = make()
    refresh(backend)
    record = backend.records()[0]
    backend.edit(record["id"], record["revision"], dict(record["values"], host="App host"), {})
    source.rows[0]["host"] = "Calendar host"
    refresh(backend)
    record = backend.records()[0]
    backend.edit(record["id"], record["revision"], record["values"].copy(), {"host": "app"})
    refresh(backend)
    assert backend.records()[0]["values"]["host"] == "App host"
    assert not backend.records()[0]["conflicts"]


def test_stale_admin_form_cannot_overwrite_new_calendar_change():
    app, source, backend = make()
    client = app.test_client()
    csrf = login(client)
    client.get("/admin")
    old = backend.records()[0]
    source.rows[0]["host"] = "Changed host"
    response = client.post("/admin/meetings/" + old["id"], data=form(old, csrf, topic="Would overwrite"))
    assert response.status_code == 409
    assert 'disabled>Save changes' in response.text
    assert backend.records()[0]["values"]["host"] == "Changed host"
    assert backend.records()[0]["values"]["topic"] != "Would overwrite"


def test_source_failure_keeps_data_and_blocks_admin_write():
    app, source, backend = make()
    client = app.test_client()
    csrf = login(client)
    client.get("/admin")
    record = backend.records()[0]
    source.fail = True
    result = client.post("/admin/meetings/" + record["id"], data=form(record, csrf, host="Changed"))
    assert result.status_code == 409
    assert backend.records()[0] == record
    assert "last successful schedule" in client.get("/").text


def test_removed_calendar_date_requires_explicit_keep_or_cancel():
    _, source, backend = make()
    refresh(backend)
    source.rows.clear()
    # Preserve schema for a valid empty source.
    from schedule.data import HeaderRows, FIELDS
    source.read = lambda: HeaderRows([], FIELDS)
    refresh(backend)
    record = backend.records()[0]
    assert "_removed" in record["conflicts"]
    backend.edit(record["id"], record["revision"], record["values"].copy(), {"_removed": "cancel"})
    refresh(backend)
    assert backend.records()[0]["values"]["status"] == "canceled"
    assert not backend.records()[0]["conflicts"]


def test_date_edit_preserves_meeting_identity_and_attendance():
    app, _, backend = make()
    client = app.test_client()
    client.get("/")
    record = backend.records()[0]
    with client.session_transaction() as session:
        csrf = session["csrf"]
    client.post("/attendance/" + record["id"], data={
        "csrf": csrf, "action": "all", "household": "Example", "people": "Alex, Sam"})
    backend.edit(record["id"], record["revision"], dict(record["values"], date="2026-10-03"), {})
    html = client.get("/").text
    assert "2 people going" in html and "October 3" in html
    assert backend.records()[0]["id"] == record["id"]


def test_sheet_outage_retains_pending_then_recovers_without_duplicate_write():
    _, _, backend = make()
    publisher = Publisher()
    backend.publisher = publisher
    refresh(backend)
    assert backend.status()["pending"]
    assert publisher.remote is None
    publisher.create(backend.export())
    with backend.store.connection:
        backend.set_meta("published_hash", digest(publisher.remote))
    record = backend.records()[0]
    publisher.fail = True
    backend.edit(record["id"], record["revision"], dict(record["values"], notes="Local edit"), {})
    assert backend.status()["pending"] and backend.status()["error"]
    publisher.fail, publisher.lose_ack = False, True
    assert not backend.publish(force=True)
    assert backend.publish(force=True)
    assert not backend.status()["pending"]
    assert publisher.writes == 1


def test_foreign_backend_change_is_not_overwritten():
    _, _, backend = make()
    refresh(backend)
    publisher = Publisher(backend.export())
    backend.publisher = publisher
    with backend.store.connection:
        backend.set_meta("published_hash", digest(publisher.remote))
    publisher.remote[0]["record"]["values"]["host"] = "Another server"
    record = backend.records()[0]
    backend.edit(record["id"], record["revision"], dict(record["values"], topic="Local topic"), {})
    assert publisher.writes == 0
    assert "No data was overwritten" in backend.status()["error"]


def test_fresh_backend_restores_schedule_and_cookie_household_without_cookie_secret():
    app, _, backend = make()
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf, raw = session["csrf"], session["household_id"]
    record = backend.records()[0]
    client.post("/attendance/" + record["id"], data={
        "csrf": csrf, "action": "all", "household": "Example", "people": "Alex, Sam"})
    backend.edit(record["id"], record["revision"], dict(record["values"], topic="App topic"), {})
    payload = backend.export()
    assert raw not in json.dumps(payload)
    assert payload[0]["responses"][0]["id"] == hashlib.sha256(raw.encode()).hexdigest()
    other, _, restored = make()
    restored.publisher = Publisher(payload)
    refresh(restored)
    assert restored.records()[0]["values"]["topic"] == "App topic"
    store = other.extensions["attendance"].store
    assert store.household(raw)["name"] == "Example"
    assert store.summaries([record["id"]], raw)[record["id"]]["people"] == 2
    store.save(raw, record["id"], "none", "", "", [], NOW.isoformat())
    assert store.summaries([record["id"]], raw)[record["id"]]["people"] == 0


def test_init_command_creates_once_without_replacing_existing_tab():
    app, _, backend = make()
    publisher = Publisher()
    backend.publisher = publisher
    result = app.test_cli_runner().invoke(args=["init-sheet-backend"])
    assert result.exit_code == 0 and publisher.remote
    original = copy.deepcopy(publisher.remote)
    result = app.test_cli_runner().invoke(args=["init-sheet-backend"])
    assert result.exit_code != 0 and publisher.remote == original


def test_sheet_writer_targets_only_new_tab_and_uses_literal_strings():
    _, _, backend = make()
    refresh(backend)
    payload = backend.export()
    payload[0]["record"]["values"]["notes"] = "=IMPORTXML(should_not_run)"
    adapter = SheetBackend("fake-sheet", "fake-key", "App Backend", "'Calendar'!A1:J200")
    calls = []
    adapter.sheets = lambda: [{"properties": {"sheetId": 12, "title": "Calendar"}}]
    adapter.request = lambda *args, **kwargs: calls.append((args, kwargs)) or {}
    assert adapter.create(payload) == 13
    requests = calls[0][1]["json"]["requests"]
    assert requests[0]["addSheet"]["properties"]["title"] == "App Backend"
    write = requests[1]["updateCells"]
    assert write["range"]["sheetId"] == 13
    assert write["rows"][1]["values"][9]["userEnteredValue"] == {"stringValue": "=IMPORTXML(should_not_run)"}
    with pytest.raises(ValueError):
        SheetBackend("fake", "fake", "Calendar", "'Calendar'!A1:J200")


def test_sheet_read_rejects_manual_cell_changes():
    _, _, backend = make()
    refresh(backend)
    adapter = SheetBackend("fake", "fake", "App Backend", "'Calendar'!A1:J200")
    adapter.properties = lambda: {"sheetId": 1}
    table = adapter.table(backend.export())
    adapter.request = lambda *args, **kwargs: {"values": table}
    assert adapter.read() == backend.export()
    table[1][4] = "Manually edited backend topic"
    with pytest.raises(DataError):
        adapter.read()

def test_pending_schedule_survives_restart_with_stale_source(local_path):
    database = str(local_path / "durable.sqlite3")
    first, source, backend = make(RSVP_DATABASE=database)
    refresh(backend)
    record = backend.records()[0]
    backend.edit(record["id"], record["revision"], dict(record["values"], topic="Persisted app edit"), {})
    backend.store.connection.close()
    source.fail = True
    second, _, restored = make(source, RSVP_DATABASE=database)
    response = second.test_client().get("/")
    assert response.status_code == 200
    assert "Persisted app edit" in response.text and "last successful schedule" in response.text
    restored.store.connection.close()


def test_invalid_restoration_rolls_back_without_partial_households():
    first, _, original = make()
    refresh(original)
    payload = original.export()
    payload[0]["record"]["values"]["date"] = "not-a-date"
    app, _, backend = make()
    backend.publisher = Publisher(payload)
    assert refresh(backend).stale
    assert not backend.records()


def test_admin_password_setup_writes_only_hash_and_invalidates_session(local_path):
    hash_path = local_path / "admin.hash"
    app, _, _ = make(ADMIN_PASSWORD_HASH="", ADMIN_PASSWORD_FILE=str(hash_path))
    client = app.test_client()
    assert "not been configured" in client.get("/admin/login").text
    result = app.test_cli_runner().invoke(args=["set-admin-password", "--password", PASSWORD])
    assert result.exit_code == 0
    assert PASSWORD not in hash_path.read_text()
    login(client)
    assert client.get("/admin").status_code == 200
    result = app.test_cli_runner().invoke(args=["set-admin-password", "--password", "another-fictional-password"])
    assert result.exit_code == 0
    assert client.get("/admin").status_code == 302


def test_backend_member_write_updates_sheet_counts_without_cookie_token():
    app, _, backend = make()
    client = app.test_client()
    client.get("/")
    backend.publisher = Publisher(backend.export())
    with backend.store.connection:
        backend.set_meta("published_hash", digest(backend.publisher.remote))
    record = backend.records()[0]
    with client.session_transaction() as session:
        csrf, token = session["csrf"], session["household_id"]
    response = client.post("/attendance/" + record["id"], data={
        "csrf": csrf, "action": "all", "household": "Example", "people": "Alex, Sam"},
        headers={"Accept": "application/json"})
    assert response.status_code == 200 and not backend.status()["pending"]
    table = SheetBackend.table(backend.publisher.remote)
    assert table[1][12:15] == [2, 1, 0]
    assert token not in json.dumps(table)


@pytest.fixture
def local_path():
    cache = (ROOT / ".cache").resolve()
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="backend-test-", dir=cache) as folder:
        path = Path(folder).resolve()
        assert path.parent == cache
        yield path
