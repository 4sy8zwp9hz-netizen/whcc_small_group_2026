"""Independent writers and migration regressions; no Google calls or real data."""
import copy
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
import pytest
from requests.exceptions import HTTPError
from schedule.backend import DataError, digest, encode
from schedule.login_limiter import LoginLimiter
from schedule.sheet_backend import SheetBackend
from schedule.source_identity import source_title
from schedule.state_patch import entities
from tools.create_deployment_secrets import signing_key, main as secrets_main
from test_backend_admin import make, Source, Publisher, NOW, PASSWORD, PASSWORD_HASH, local_path
from test_cloud_run import HASH, GROUP, group_login


class Transport:
    def __init__(self, items, barrier=None):
        self.rows = SheetBackend.table(items)
        self.lock = threading.Lock()
        self.barrier = barrier
        self.gets = 0
        self.posts = []
        self.quota = None
        self.fail_gets = 0
        self.delay = False
        self.pending = []
        self.lose_ack = False
    def request(self, method, suffix="", **kwargs):
        if method == "GET":
            with self.lock:
                self.gets += 1
                if self.fail_gets or (self.quota is not None and self.gets > self.quota):
                    self.fail_gets = max(0, self.fail_gets - 1)
                    error = HTTPError("fictional quota")
                    error.response = type("Response", (), {"status_code": 429})()
                    raise error
                if "/values/" in suffix:
                    return {"values": copy.deepcopy(self.rows)}
                return {"sheets": [{"properties": {"title": "App Backend", "sheetId": 123,
                                                     "gridProperties": {"rowCount": 1000}}}]}
        assert suffix == ":batchUpdate", "Only typed append writes permitted"
        mutation = kwargs["json"]["requests"][0]
        assert set(mutation) == {"appendCells"}, "No full-tab writes permitted"
        append = mutation["appendCells"]
        assert append["sheetId"] == 123 and append["fields"] == "userEnteredValue"
        if self.barrier:
            self.barrier.wait(timeout=10)
        with self.lock:
            row = [cell["userEnteredValue"]["stringValue"] for cell in append["rows"][0]["values"]]
            self.posts.append(row)
            if self.delay:
                self.pending.append(row)
                raise TimeoutError("delayed unknown acknowledgment")
            self.rows.append(row)
            if self.lose_ack:
                self.lose_ack = False
                raise TimeoutError("lost acknowledgment")
        return {}
    def reveal(self):
        with self.lock:
            self.rows.extend(self.pending)
            self.pending = []
            self.delay = False
    def adapter(self):
        adapter = SheetBackend("fictional-sheet", "", "App Backend", "'Schedule'!A1:J500")
        adapter.request = self.request
        return adapter


def make_google(source_range="'Schedule'!A1:J500", **extra):
    return make(DATA_SOURCE="google", GOOGLE_SHEET_ID="fictional-sheet",
                GOOGLE_SHEET_RANGE=source_range, SECRET_KEY="fictional-stable-key-at-least-32-characters", **extra)


def legacy_payload(title="'Schedule'"):
    app, source, backend = make_google(title + "!A1:J500")
    backend.cache.get()
    items = backend.export()
    identity = hashlib.sha256(("google\0fictional-sheet\0" + title + "\0" + "2026-10-02").encode()).hexdigest()[:32]
    items[0]["record"]["id"] = identity
    profile = {"id": hashlib.sha256(b"fictional-visitor").hexdigest(), "name": "Fictional household",
               "members": [{"id": "a"*24, "name": "Alex"}]}
    items[0]["responses"] = [{**profile, "attending": ["a"*24], "updated_at": NOW.isoformat()}]
    items[0]["households"] = [profile]
    return items


@pytest.mark.parametrize("old,new", [("'Schedule'", "Schedule"), ("Schedule", "'Schedule'"),
                                      ("'Leader''s Schedule'", "Leader's Schedule")])
def test_equivalent_range_preserves_restored_ids_and_historical_responses(old, new):
    items = legacy_payload(old)
    app, _, backend = make_google(new + "!A1:J900")
    backend.publisher, backend.strict = Publisher(items), True
    snapshot = backend.cache.get()
    assert not snapshot.stale and len(backend.records()) == 1
    assert backend.records()[0]["id"] == items[0]["record"]["id"]
    assert backend.export()[0]["responses"] == items[0]["responses"]
    assert not snapshot.meetings[0].date_conflict
    client = app.test_client()
    with client.session_transaction() as session:
        session["household_id"] = "fictional-visitor"
        session["csrf"] = "fictional-csrf-token"
    assert client.post("/attendance/" + items[0]["record"]["id"],
                       data={"csrf": "fictional-csrf-token", "action": "none"}).status_code == 303
    assert backend.export()[0]["responses"][0]["attending"] == []


def test_existing_sqlite_quoted_scope_and_queued_override_survive(local_path):
    database = str(local_path / "migration.sqlite3")
    app, _, backend = make_google(RSVP_DATABASE=database)
    backend.cache.get()
    record = backend.records()[0]
    backend.edit(record["id"], record["revision"], {**record["values"], "topic": "Queued override"}, {})
    old_scope = hashlib.sha256(b"google\0fictional-sheet\0'Schedule'").hexdigest()
    with backend.store.connection:
        backend.store.connection.execute("UPDATE app_schedule SET scope=?", (old_scope,))
        backend.store.connection.execute("UPDATE app_metadata SET scope=?", (old_scope,))
    backend.store.connection.close()
    _, _, fresh = make_google("Schedule!A1:J500", RSVP_DATABASE=database)
    assert fresh.records()[0]["id"] == record["id"]
    assert fresh.cache.get().meetings[0].topic == "Queued override"
    fresh.store.connection.close()


@pytest.mark.parametrize("endpoint,password,config", [("/group/login", GROUP, {"GROUP_ACCESS_PASSWORD_HASH": HASH}),
                                                       ("/admin/login", PASSWORD, {})])
def test_one_browser_cannot_exhaust_other_login_allowance(endpoint, password, config):
    app, _, _ = make(**config)
    bad, good = app.test_client(), app.test_client()
    bad.get(endpoint)
    with bad.session_transaction() as session:
        token = session["csrf"]
    for _ in range(10):
        assert bad.post(endpoint, data={"csrf": token, "password": "wrong"}).status_code == 401
    assert bad.post(endpoint, data={"csrf": token, "password": password}).status_code == 429
    # Identical proxy IPs/forged headers do not combine signed browser buckets.
    for _ in range(15):
        good.get(endpoint)
        with good.session_transaction() as session:
            token = session["csrf"]
        assert good.post(endpoint, data={"csrf": token, "password": password},
                         headers={"X-Forwarded-For": "attacker-selected-value"}).status_code == 303


def test_limiter_is_bounded_expires_and_resets_on_replacement():
    clock = [0]
    limiter = LoginLimiter(capacity=3, clock=lambda: clock[0])
    for identity in range(100):
        limiter.failure(str(identity))
    assert len(limiter.clients) == 3
    for _ in range(10):
        limiter.failure("browser")
    assert limiter.blocked("browser")
    assert not LoginLimiter().blocked("browser")
    clock[0] = 301
    assert not limiter.blocked("browser")


def writer_pair(barrier=None):
    one = make_google()
    one[2].cache.get()
    transport = Transport(one[2].export(), barrier)
    two = make_google()
    for app, _, backend in (one, two):
        backend.publisher, backend.strict = transport.adapter(), True
        assert not backend.cache.get().stale
    return one, two, transport


def form_client(app, backend, name):
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        token = session["csrf"]
    key = backend.records()[0]["id"]
    return client, key, {"csrf": token, "action": "all", "household": name, "people": name + " person"}


def test_two_independent_rsvp_writers_reject_stale_and_recover_both_after_retry():
    one, two, transport = writer_pair()
    pairs = [form_client(app, backend, name) for (app, _, backend), name in
             zip((one, two), ("Fictional A", "Fictional B"))]
    transport.barrier = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda item: item[0].post("/attendance/" + item[1], data=item[2]), pairs))
    assert sorted(r.status_code for r in responses) == [303, 503]
    transport.barrier = None
    loser = next(i for i, response in enumerate(responses) if response.status_code == 503)
    client, key, values = pairs[loser]
    assert client.post("/attendance/" + key, data=values).status_code == 303
    # Empty-cache restart, using the real append adapter and original browser cookie.
    app, _, fresh = make_google()
    fresh.publisher, fresh.strict = transport.adapter(), True
    restored = app.test_client()
    original = pairs[0][0].get_cookie(app.config["SESSION_COOKIE_NAME"])
    restored.set_cookie(app.config["SESSION_COOKIE_NAME"], original.value)
    assert restored.get("/").status_code == 200
    assert len(fresh.export()[0]["responses"]) == 2
    with restored.session_transaction() as session:
        visitor = session["household_id"]
    assert fresh.store.household(visitor)["name"] == "Fictional A"


def test_admin_and_rsvp_independent_writers_do_not_overwrite_acknowledged_change():
    one, two, transport = writer_pair()
    client, key, values = form_client(two[0], two[2], "Fictional RSVP")
    record = copy.deepcopy(one[2].records()[0])
    transport.barrier = threading.Barrier(2)
    def edit():
        try:
            one[2].edit(key, record["revision"], {**record["values"], "topic": "Fictional admin edit"}, {})
            return 303
        except DataError:
            return 503
    with ThreadPoolExecutor(max_workers=2) as pool:
        admin_result = pool.submit(edit)
        rsvp_result = pool.submit(lambda: client.post("/attendance/" + key, data=values).status_code)
        result = [admin_result.result(), rsvp_result.result()]
    assert sorted(result) == [303, 503]
    transport.barrier = None
    if result[0] == 503:
        with one[2].store.lock, one[2].store.connection:
            one[2].refresh_remote()
        record = one[2].records()[0]
        one[2].edit(key, record["revision"], {**record["values"], "topic": "Fictional admin edit"}, {})
    else:
        assert client.post("/attendance/" + key, data=values).status_code == 303
    durable = transport.adapter().read()
    assert durable[0]["record"]["values"]["topic"] == "Fictional admin edit"
    assert len(durable[0]["responses"]) == 1


def test_delayed_unknown_ack_retries_same_event_and_restores_after_error():
    one, _, transport = writer_pair()
    app, _, backend = one
    client, key, values = form_client(app, backend, "Fictional delayed")
    transport.delay = True
    with patch("schedule.sheet_backend.time.sleep"):
        result = client.post("/attendance/" + key, data=values)
    assert result.status_code == 503 and len(transport.pending) == 2
    assert transport.pending[0] == transport.pending[1]
    assert not backend.export()[0]["responses"]
    cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"]).value
    fresh_app, _, fresh = make_google()
    fresh.publisher, fresh.strict = transport.adapter(), True
    restored = fresh_app.test_client()
    restored.set_cookie(app.config["SESSION_COOKIE_NAME"], cookie)
    assert restored.get("/").status_code == 200  # restart before delayed rows become visible
    assert not fresh.export()[0]["responses"]
    transport.reveal()
    fresh.invalidate()
    assert restored.get("/").status_code == 200
    assert len(fresh.export()[0]["responses"]) == 1
    with restored.session_transaction() as session:
        token = session["csrf"]
    assert restored.post("/attendance/" + key, data={"csrf": token, "action": "none"}).status_code == 303


def test_quota_burst_uses_two_values_reads_per_rsvp_and_bounded_429_retry():
    one, _, transport = writer_pair()
    one[2].publisher.read()  # warm metadata separately from mutation cost
    transport.quota = 60
    before = transport.gets
    for number in range(8):
        client, key, values = form_client(one[0], one[2], "Fictional " + str(number))
        assert client.post("/attendance/" + key, data=values).status_code == 303
    assert transport.gets - before == 16  # warm metadata, before-write and receipt reads
    client, key, values = form_client(one[0], one[2], "Fictional retry")
    transport.fail_gets = 1
    with patch("schedule.sheet_backend.time.sleep"):
        assert client.post("/attendance/" + key, data=values).status_code == 303
    transport.fail_gets = 10
    before = transport.gets
    with patch("schedule.sheet_backend.time.sleep"), pytest.raises(HTTPError):
        one[2].publisher.read()
    assert transport.gets - before == 2


def test_receipt_429_does_not_duplicate_or_lose_accepted_event():
    one, _, transport = writer_pair()
    adapter = one[2].publisher
    base = adapter.read()
    desired = copy.deepcopy(base)
    desired[0]["record"]["values"]["notes"] = "Fictional 429 receipt"
    original = transport.request
    def request(method, suffix="", **kwargs):
        result = original(method, suffix, **kwargs)
        if method == "POST":
            transport.fail_gets = 1
        return result
    adapter.request = request
    with patch("schedule.sheet_backend.time.sleep"):
        assert adapter.commit(desired, base) == desired
    assert len(transport.posts) == 1
    assert transport.adapter().read() == desired


def test_large_rosters_use_small_toggle_clear_and_admin_payloads():
    source = Source()
    source.rows.append({**source.rows[0], "date": "2026-10-09", "topic": "Second fictional meeting"})
    one = make_google(source=source)
    one[2].cache.get()
    transport = Transport(one[2].export())
    adapter = transport.adapter()
    state = adapter.read()
    for number in range(20):
        profile = {"id": hashlib.sha256(str(number).encode()).hexdigest(),
                   "name": "Fictional " + str(number),
                   "members": [{"id": hashlib.sha256(f"{number}:{i}".encode()).hexdigest()[:24],
                                "name": str(i).zfill(2) + "\U0001f600"*38} for i in range(20)]}
        desired = copy.deepcopy(state)
        desired[0]["households"].append(profile)
        desired[0]["households"].sort(key=lambda p: p["id"])
        desired[0]["responses"].append({**profile, "attending": [m["id"] for m in profile["members"]], "updated_at": NOW.isoformat()})
        desired[0]["responses"].sort(key=lambda r: r["id"])
        desired[1]["responses"].append({**profile, "attending": [profile["members"][0]["id"]], "updated_at": NOW.isoformat()})
        desired[1]["responses"].sort(key=lambda r: r["id"])
        state = adapter.commit(desired, state)
    assert len(encode(state)) > 49000
    desired = copy.deepcopy(state)
    desired[0]["responses"][0]["attending"].pop()
    state = adapter.commit(desired, state)
    payload = json.loads(transport.posts[-1][16])["patch"]
    assert not payload["records"] and not payload["profiles"] and len(payload["responses"]) == 1
    assert len(transport.posts[-1][16]) < 1500
    desired = copy.deepcopy(state)
    cleared = desired[0]["responses"].pop(0)["id"]
    state = adapter.commit(desired, state)
    assert len(transport.posts[-1][16]) < 1000
    desired = copy.deepcopy(state)
    desired[0]["record"]["values"]["notes"] = "Small admin edit"
    state = adapter.commit(desired, state)
    assert len(transport.posts[-1][16]) < 5000
    fresh_app, _, fresh = make_google()
    fresh.publisher, fresh.strict = transport.adapter(), True
    fresh.cache.get()
    assert len(fresh.export()[0]["households"]) == 20
    assert len(fresh.export()[0]["responses"]) == 19
    assert len(fresh.export()[1]["responses"]) == 20
    assert cleared in {p["id"] for p in fresh.export()[0]["households"]}


def test_full_tab_replacement_denied_before_any_request():
    one, _, transport = writer_pair()
    base = one[2].publisher.read()
    desired = copy.deepcopy(base)
    desired[0]["record"]["values"]["notes"] = "Accepted history"
    one[2].publisher.commit(desired, base)
    before = copy.deepcopy(transport.rows)
    with pytest.raises(DataError, match="disabled"):
        one[2].publisher.write(base)
    assert transport.rows == before and transport.adapter().read() == desired


def test_migration_key_selection_never_generates_and_fresh_refuses_existing(local_path, monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("RSVP_SECRET_FILE", raising=False)
    existing = "fictional-existing-signing-key-32-characters"
    (local_path / "private").mkdir()
    (local_path / "private/session.key").write_text(existing)
    with patch("tools.create_deployment_secrets.secrets.token_hex", side_effect=AssertionError("Must not generate")):
        assert signing_key(local_path, "migrate") == existing
    with pytest.raises(ValueError, match="existing"):
        signing_key(local_path, "fresh")
    monkeypatch.setenv("SECRET_KEY", existing + "environment")
    assert signing_key(local_path, "migrate") == existing + "environment"
    with pytest.raises(ValueError, match="disagrees"):
        signing_key(local_path, "migrate", key_file="private/session.key")


def test_migration_missing_key_stops_and_helper_requires_explicit_mode(local_path):
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="No new key"):
            signing_key(local_path, "migrate")
        with pytest.raises(SystemExit):
            secrets_main([], root=local_path)
    assert not (local_path / "private/deployment-secrets").exists()


@pytest.mark.parametrize("same_key,new_host,reconnected", [(True, "old.example", True),
                                                           (False, "old.example", False),
                                                           (True, "new.example", False)])
def test_key_preservation_and_browser_origin_are_separate(same_key, new_host, reconnected):
    app, source, backend = make_google()
    backend.cache.get()
    transport = Transport(backend.export())
    backend.publisher, backend.strict = transport.adapter(), True
    client = app.test_client()
    client.get("/", base_url="http://old.example")
    with client.session_transaction(base_url="http://old.example") as session:
        token = session["csrf"]
    key = backend.records()[0]["id"]
    assert client.post("/attendance/" + key, base_url="http://old.example",
                       data={"csrf": token, "action": "all", "household": "Fictional migration", "people": "Alex"}).status_code == 303
    cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"], domain="old.example")
    fresh_app, _, fresh = make(source=source, DATA_SOURCE="google", GOOGLE_SHEET_ID="fictional-sheet",
                               GOOGLE_SHEET_RANGE="Schedule!A1:J500",
                               SECRET_KEY=app.secret_key if same_key else "fictional-different-key-32-characters")
    fresh.publisher, fresh.strict = transport.adapter(), True
    fresh_client = fresh_app.test_client()
    fresh_client.set_cookie(app.config["SESSION_COOKIE_NAME"], cookie.value, domain="old.example")
    assert fresh_client.get("/", base_url="http://" + new_host).status_code == 200
    with fresh_client.session_transaction(base_url="http://" + new_host) as session:
        remembered = fresh.store.household(session["household_id"])
    assert bool(remembered) == reconnected
    assert len(fresh.export()[0]["responses"]) == 1  # historical response survives even without browser reconnection


def test_secret_helper_migration_copies_effective_key_without_display(local_path, monkeypatch, capsys):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("RSVP_SECRET_FILE", raising=False)
    key = "fictional-effective-env-secret-at-least-32-characters"
    (local_path / ".env").write_text("SECRET_KEY=" + key)
    (local_path / ".env.private").write_text("DATA_SOURCE=google")
    with patch("tools.create_deployment_secrets.getpass", side_effect=["fictional-group-password"]*2 + ["fictional-admin-password"]*2), patch("tools.create_deployment_secrets.secrets.token_hex", side_effect=AssertionError("No generated signing key")):
        secrets_main(["--mode", "migrate", "--env-file", ".env.private"], root=local_path)
    assert (local_path / "private/deployment-secrets/secret-key").read_text() == key
    assert key not in capsys.readouterr().out


def test_invalid_duplicate_or_inconsistent_profiles_fail_before_restore():
    values = legacy_payload()
    values[0]["households"].append(copy.deepcopy(values[0]["households"][0]))
    with pytest.raises(DataError, match="duplicate"):
        SheetBackend.validate(values)
    values = legacy_payload()
    values[0]["responses"][0]["name"] = "Conflicting fictional name"
    with pytest.raises(DataError, match="inconsistent"):
        SheetBackend.validate(values)


def test_permanent_append_error_is_not_retried_or_acknowledged():
    one, _, transport = writer_pair()
    adapter = one[2].publisher
    base = adapter.read()
    desired = copy.deepcopy(base)
    desired[0]["record"]["values"]["notes"] = "Unconfirmed permission failure"
    posts = []
    def request(method, suffix="", **kwargs):
        if method == "POST":
            posts.append(kwargs)
            error = HTTPError("fictional forbidden")
            error.response = type("Response", (), {"status_code": 403})()
            raise error
        return transport.request(method, suffix, **kwargs)
    adapter.request = request
    with pytest.raises(HTTPError):
        adapter.commit(desired, base)
    assert len(posts) == 1 and transport.adapter().read() == base


def test_mixed_legacy_and_granular_events_restore_same_ids_and_profiles():
    from schedule.state_patch import apply
    legacy = legacy_payload()
    legacy[0].pop("households")
    changed = copy.deepcopy(legacy)
    changed[0]["record"]["values"]["notes"] = "Existing version-one override"
    transport = Transport(legacy)
    event = {"_event": 1, "id": "b"*32, "expected": digest(legacy), "changes": changed}
    transport.rows.append(SheetBackend.event_row(event))
    adapter = transport.adapter()
    base = adapter.read()
    assert base == changed
    desired = apply(base, {"records": [], "profiles": [], "responses": [], "cleared": []})
    desired[0]["record"]["values"]["notes"] = "New granular override"
    assert adapter.commit(desired, base) == desired
    app, _, fresh = make_google("Schedule!A1:J500")
    fresh.publisher, fresh.strict = transport.adapter(), True
    assert not fresh.cache.get().stale
    assert fresh.records()[0]["id"] == legacy[0]["record"]["id"]
    assert fresh.store.household("fictional-visitor")["members"][0]["id"] == "a"*24


def test_accepted_commit_with_newer_verified_state_is_not_reported_as_lost():
    one, two, transport = writer_pair()
    client, key, values = form_client(one[0], one[2], "Fictional first writer")
    original = transport.request
    triggered = []
    def request(method, suffix="", **kwargs):
        result = original(method, suffix, **kwargs)
        if method == "POST" and not triggered:
            triggered.append(True)
            with two[2].store.lock, two[2].store.connection:
                two[2].refresh_remote()
            record = two[2].records()[0]
            two[2].edit(key, record["revision"], {**record["values"], "notes": "Newer accepted note"}, {})
        return result
    one[2].publisher.request = request
    assert client.post("/attendance/" + key, data=values).status_code == 303
    assert one[2].records()[0]["values"]["notes"] == "Newer accepted note"
    durable = transport.adapter().read()
    assert len(durable[0]["responses"]) == 1
    assert durable[0]["record"]["values"]["notes"] == "Newer accepted note"
