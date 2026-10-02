"""Fictional-only Cloud Run configuration, isolation and recovery contracts."""
import copy
import re
import runpy
from unittest.mock import patch
import pytest
from werkzeug.security import generate_password_hash
from schedule import create_app
from schedule.backend import DataError, digest
from schedule.google_credentials import credentials_for
from schedule.sheet_backend import SheetBackend
from test_backend_admin import make, Publisher, Source, PASSWORD_HASH, NOW, local_path

GROUP = "fictional-group-password"
HASH = generate_password_hash(GROUP, method="pbkdf2:sha256:1000")


def group_login(client):
    client.get("/group/login")
    with client.session_transaction() as session:
        csrf = session["csrf"]
    assert client.post("/group/login", data={"csrf": csrf, "password": GROUP}).status_code == 303
    with client.session_transaction() as session:
        return session["csrf"]


def production(**extra):
    return create_app({"TESTING": True, "APP_ENV": "production", "SECRET_KEY": "fictional-stable-secret-key-32-characters",
                       "GROUP_ACCESS_PASSWORD_HASH": HASH, "ADMIN_PASSWORD_HASH": PASSWORD_HASH,
                       "DATA_SOURCE": "google", "GOOGLE_SHEET_ID": "fictional-sheet-id",
                       "GOOGLE_SHEET_RANGE": "'Schedule'!A1:J500", "GOOGLE_APPLICATION_CREDENTIALS": "",
                       "SCHEDULE_EDITING": True, "BACKEND_SHEET_ENABLED": True, **extra},
                      source=Source(), now=lambda: NOW)


def test_health_is_public_fast_and_has_no_cookie_or_google_call():
    with patch.object(SheetBackend, "read", side_effect=AssertionError("No API call")):
        app = production()
        result = app.test_client().get("/health")
    assert result.status_code == 200 and result.json == {"status": "ok"}
    assert "Set-Cookie" not in result.headers
    assert app.config["SESSION_COOKIE_SECURE"] and app.extensions["backend"].strict


@pytest.mark.parametrize("key,value", [("SECRET_KEY", None), ("GROUP_ACCESS_PASSWORD_HASH", ""),
    ("ADMIN_PASSWORD_HASH", "plaintext"), ("BACKEND_SHEET_ENABLED", False), ("DATA_SOURCE", "csv")])
def test_production_rejects_incomplete_security(key, value):
    with pytest.raises(ValueError):
        production(**{key: value})


def test_group_gate_covers_private_routes_and_independent_admin():
    app, _, backend = make(GROUP_ACCESS_PASSWORD_HASH=HASH)
    client = app.test_client()
    for path in ("/", "/past", "/admin", "/admin/login"):
        assert client.get(path).location.endswith("/group/login")
    assert client.post("/attendance/unknown").status_code == 401
    assert client.post("/group/login", data={"password": GROUP}).status_code == 400
    csrf = group_login(client)
    assert client.get("/").status_code == 200
    assert client.get("/admin").location.endswith("/admin/login")
    assert client.post("/group/logout", data={"csrf": "bad"}).status_code == 400
    assert client.post("/group/logout", data={"csrf": csrf}).status_code == 303
    assert client.get("/").location.endswith("/group/login")


def test_group_throttle_and_password_rotation():
    app, _, _ = make(GROUP_ACCESS_PASSWORD_HASH=HASH)
    client = app.test_client()
    csrf = group_login(client)
    app.config["GROUP_ACCESS_PASSWORD_HASH"] = generate_password_hash("changed-fictional-password", method="pbkdf2:sha256:1000")
    assert client.get("/").location.endswith("/group/login")
    for _ in range(9):
        assert client.post("/group/login", data={"csrf": csrf, "password": "wrong"}).status_code == 401
    assert client.post("/group/login", data={"csrf": csrf, "password": GROUP}).status_code == 429


def test_adc_and_explicit_local_credentials_are_lazy_and_scoped():
    with patch("google.auth.default", return_value=("adc", "project")) as default:
        assert credentials_for() == "adc"
        default.assert_called_once_with(scopes=["https://www.googleapis.com/auth/spreadsheets"])
    with patch("google.oauth2.service_account.Credentials.from_service_account_file", return_value="local") as local:
        assert credentials_for("fictional.json", readonly=True) == "local"
        local.assert_called_once_with("fictional.json", scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])


def test_proxy_trust_is_only_scheme_and_cookie_is_secure():
    app = production(TRUST_PROXY=True)
    result = app.test_client().get("/group/login", headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "attacker.invalid"})
    assert "Secure" in result.headers["Set-Cookie"]
    assert "attacker.invalid" not in result.text
    assert app.wsgi_app.x_for == app.wsgi_app.x_host == 0
    with pytest.raises(ValueError):
        make(TRUST_PROXY=True)


def seed(**config):
    app, source, backend = make(SECRET_KEY="fictional-stable-secret-key-32-characters", **config)
    backend.cache.get()
    publisher = Publisher(backend.export())
    backend.publisher = publisher
    backend.strict = True
    return app, source, backend, publisher


def test_strict_failed_write_rolls_back_and_does_not_acknowledge():
    app, _, backend, publisher = seed()
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf = session["csrf"]
    key = backend.records()[0]["id"]
    with patch.object(publisher, "write", side_effect=TimeoutError):
        result = client.post("/attendance/" + key, data={"csrf": csrf, "action": "all", "household": "Fictional family", "people": "Alex, Sam"}, headers={"Accept": "application/json"})
    assert result.status_code == 503 and "not confirmed" in result.json["error"]
    assert not backend.export()[0]["responses"]


def test_empty_filesystem_restores_cookie_household_rsvp_and_override(local_path):
    app, source, backend, publisher = seed(RSVP_DATABASE=str(local_path / "old.sqlite3"))
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf = session["csrf"]
    key = backend.records()[0]["id"]
    assert client.post("/attendance/" + key, data={"csrf": csrf, "action": "all", "household": "Fictional family", "people": "Alex, Sam"}).status_code == 303
    record = backend.records()[0]
    backend.edit(key, record["revision"], {**record["values"], "topic": "Durable override"}, {})
    cookie = client.get_cookie(app.config["SESSION_COOKIE_NAME"]).value
    # Close the old connection and create a truly empty SQLite file, not a retained process cache.
    backend.store.connection.close()
    (local_path / "old.sqlite3").unlink()
    fresh, _, restored = make(source=source, SECRET_KEY=app.secret_key, RSVP_DATABASE=str(local_path / "empty.sqlite3"))
    restored.publisher, restored.strict = publisher, True
    new_client = fresh.test_client()
    new_client.set_cookie(fresh.config["SESSION_COOKIE_NAME"], cookie)
    response = new_client.get("/")
    assert response.status_code == 200 and "Durable override" in response.text and "Fictional family" in response.text
    with new_client.session_transaction() as session:
        csrf = session["csrf"]
    assert new_client.post("/attendance/" + key, data={"csrf": csrf, "action": "none"}).status_code == 303
    assert publisher.remote[0]["responses"][0]["attending"] == []
    restored.store.connection.close()


def test_cold_instance_uses_backend_when_original_source_fails():
    _, source, backend, publisher = seed()
    source.fail = True
    _, _, fresh = make(source=source)
    fresh.publisher, fresh.strict = publisher, True
    snapshot = fresh.cache.get()
    assert snapshot.stale and snapshot.meetings[0].topic == "Fictional gathering"


def test_append_log_rejects_overlapping_stale_writer_and_deduplicates():
    _, _, backend, _ = seed()
    base = backend.export()
    first, second = copy.deepcopy(base), copy.deepcopy(base)
    first[0]["record"]["values"]["topic"] = "First writer"
    second[0]["record"]["values"]["topic"] = "Stale second writer"
    one = {"id": "a"*32, "expected": digest(base), "changes": first}
    two = {"id": "b"*32, "expected": digest(base), "changes": second}
    state, receipts = SheetBackend.replay(base, [one, two, one])
    assert state == first and receipts == {"a"*32: True, "b"*32: False}
    with pytest.raises(DataError):
        SheetBackend.replay(base, [one, {**one, "changes": second}])


def test_gunicorn_port_and_single_process(monkeypatch):
    monkeypatch.setenv("PORT", "9099")
    values = runpy.run_path("gunicorn.conf.py")
    assert values["bind"] == "0.0.0.0:9099"
    assert (values["workers"], values["threads"], values["timeout"]) == (1, 4, 120)


def test_real_adapter_append_handles_lost_ack_and_never_rewrites():
    _, _, backend, _ = seed()
    base = backend.export()
    desired = copy.deepcopy(base)
    desired[0]["record"]["values"]["topic"] = "Confirmed append"
    adapter = SheetBackend("fictional", "", "App Backend", "'Schedule'!A1:J500")
    table = adapter.table(base)
    calls = []
    def request(method, suffix="", **kwargs):
        calls.append((method, suffix, kwargs))
        if suffix.endswith(":append"):
            table.extend(kwargs["json"]["values"])
            raise TimeoutError("acknowledgment lost")
        if "/values/" in suffix:
            return {"values": copy.deepcopy(table)}
        return {"sheets": [{"properties": {"title": "App Backend"}}]}
    adapter.request = request
    adapter.commit(desired, base)
    assert adapter.read() == desired
    write = next(call for call in calls if call[0] == "POST")
    assert write[2]["params"]["valueInputOption"] == "RAW"
    assert not any(":batchUpdate" in call[1] for call in calls)
    stale = copy.deepcopy(base)
    stale[0]["record"]["values"]["topic"] = "Losing overlap"
    with pytest.raises(DataError):
        adapter.commit(stale, base)
    assert adapter.read() == desired


def test_strict_admin_failure_preserves_last_durable_override():
    _, _, backend, publisher = seed()
    record = backend.records()[0]
    old = copy.deepcopy(record["values"])
    with patch.object(publisher, "write", side_effect=TimeoutError):
        with pytest.raises(DataError, match="not confirmed"):
            backend.edit(record["id"], record["revision"], {**old, "topic": "Unconfirmed edit"}, {})
    assert backend.records()[0]["values"] == old


def test_cleared_response_still_restores_profile():
    app, source, backend, publisher = seed()
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as session:
        csrf, visitor = session["csrf"], session["household_id"]
    key = backend.records()[0]["id"]
    client.post("/attendance/" + key, data={"csrf": csrf, "action": "all", "household": "Fictional profile", "people": "Alex"})
    assert client.post("/attendance/" + key, data={"csrf": csrf, "action": "clear"}).status_code == 303
    _, _, fresh = make(source=source)
    fresh.publisher, fresh.strict = publisher, True
    fresh.cache.get()
    assert fresh.store.household(visitor)["name"] == "Fictional profile"
    assert fresh.store.summaries([key], visitor)[key]["own"] is None


def test_invalid_environment_does_not_silently_disable_production():
    with pytest.raises(ValueError, match="APP_ENV"):
        production(APP_ENV="prodution")


def test_upload_and_image_are_allowlisted_and_exclude_nested_credentials():
    from pathlib import Path
    for name in (".dockerignore", ".gcloudignore"):
        text = Path(name).read_text()
        assert text.startswith("**\n")
        for pattern in ("!schedule/**", "!data/sample.csv", "**/*.json", "**/.env*", "**/*.sqlite*", "**/private/**"):
            assert pattern in text
    docker = Path("Dockerfile").read_text()
    assert "COPY . ." not in docker and "USER 10001" in docker
