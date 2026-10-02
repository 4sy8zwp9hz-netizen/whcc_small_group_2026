"""Fixed authorization windows using fictional data and controlled clocks."""
from types import SimpleNamespace
from unittest.mock import patch
import re

import pytest
from werkzeug.datastructures import MultiDict
from werkzeug.security import generate_password_hash
from schedule import group_access, admin
from schedule.sheet_backend import SheetBackend
from test_backend_admin import make, login as admin_login, local_path
from test_cloud_run import GROUP, HASH, production, seed


@pytest.fixture
def clock(monkeypatch):
    value = [1_800_000_000.0]
    fake = SimpleNamespace(time=lambda: value[0])
    monkeypatch.setattr(group_access, "time", fake)
    monkeypatch.setattr(admin, "time", fake)
    return value


def state(client):
    with client.session_transaction() as session:
        return dict(session)


def signin(client, remember=None, **extra):
    client.get("/group/login")
    data = MultiDict({"csrf": state(client)["csrf"], "password": GROUP, **extra})
    if remember is not None:
        data.setlist("remember_device", remember if isinstance(remember, list) else [remember])
    return client.post("/group/login", data=data)


def app_client():
    app, _, backend = make(GROUP_ACCESS_PASSWORD_HASH=HASH)
    return app, app.test_client(), backend


def test_native_unchecked_accessible_form():
    _, client, _ = app_client()
    html = client.get("/group/login").text
    checkbox = re.search(r'<input[^>]+type="checkbox"[^>]*>', html)[0]
    assert 'id="remember-device"' in checkbox and 'checked' not in checkbox
    assert '<label for="remember-device"' in html
    assert 'aria-describedby="remember-help"' in checkbox
    assert 'id="remember-help"' in html and 'shared device' in html
    assert '<script' not in html and 'method="post"' in html


@pytest.mark.parametrize("value,seconds", [(None,86400),("",86400),("on",86400),
    ("true",86400),("999999999",86400),(["30_days","30_days"],86400),
    (["30_days","on"],86400),("30_days",2592000)])
def test_only_explicit_checkbox_selects_server_duration(clock, value, seconds):
    app, client, _ = app_client()
    assert signin(client, value, duration="999999999", group_until="999999999999").status_code == 303
    assert state(client)["group_until"] == clock[0] + seconds
    assert app.permanent_session_lifetime.total_seconds() == 365 * 86400
    assert app.config["SESSION_REFRESH_EACH_REQUEST"] is False


@pytest.mark.parametrize("remember", [None,"30_days"])
def test_fixed_expiry_get_and_post(clock, remember):
    _, client, _ = app_client()
    signin(client, remember)
    deadline = state(client)["group_until"]
    clock[0] = deadline - 1
    assert client.get("/").status_code == 200
    assert 'no-store' in client.get("/").headers['Cache-Control']
    assert state(client)["group_until"] == deadline
    for offset in (0, 1):
        clock[0] = deadline + offset
        assert client.get("/").status_code == 303
        assert client.post("/attendance/unknown").status_code == 401
        assert state(client)["group_until"] == deadline


def test_existing_cookie_and_later_unchecked_login(clock):
    _, client, _ = app_client()
    signin(client)
    old = state(client)["group_until"]
    clock[0] += 100
    client.get("/group/login")
    client.get("/")
    assert state(client)["group_until"] == old
    signin(client, "30_days")
    clock[0] += 100
    signin(client)
    assert state(client)["group_until"] == clock[0] + 86400


@pytest.mark.parametrize("authenticated", [False, True])
def test_failed_login_and_csrf_never_grant_or_extend(clock, authenticated):
    _, client, _ = app_client()
    client.get("/group/login")
    if authenticated:
        signin(client, "30_days")
    before = state(client).get("group_until")
    clock[0] += 100
    assert signin(client, "30_days", password="wrong").status_code == 401
    assert state(client).get("group_until") == before
    assert signin(client, "30_days", csrf="wrong").status_code == 400
    assert state(client).get("group_until") == before


def test_checkbox_does_not_bypass_limiter(clock):
    app, client, _ = app_client()
    for i in range(10):
        assert signin(client, "30_days" if i % 2 else None, password="wrong").status_code == 401
    assert signin(client, "30_days").status_code == 429
    assert 'group_until' not in state(client)
    independent = app.test_client()
    for _ in range(12):
        assert signin(independent, "30_days").status_code == 303


def test_admin_stays_independent_and_group_relogin_does_not_revive(clock):
    _, client, _ = app_client()
    signin(client, "30_days")
    assert client.get("/admin").location.endswith('/admin/login')
    assert 'remember_device' not in client.get('/admin/login').text
    admin_login(client)
    deadline = state(client)["admin_until"]
    assert deadline == clock[0] + 1800
    clock[0] = deadline - 1
    assert client.get('/admin').status_code == 200
    signin(client, "30_days")
    assert state(client)["admin_until"] == deadline
    clock[0] = deadline
    assert client.get('/').status_code == 200
    assert client.get('/admin').location.endswith('/admin/login')
    signin(client, "30_days")
    assert client.get('/admin').location.endswith('/admin/login')


def save_household(client, backend):
    client.get('/')
    key = backend.records()[0]['id']
    result = client.post('/attendance/' + key, data={"csrf":state(client)['csrf'],
        "action":"all","household":"Fictional family","people":"Alex, Sam"})
    assert result.status_code == 303
    return key


def test_logout_csrf_and_identity_and_copied_cookie_limitation(clock):
    app, client, backend = app_client()
    signin(client, '30_days')
    key = save_household(client, backend)
    admin_login(client)
    before = state(client)
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME']).value
    assert client.get('/group/logout').status_code == 405
    assert client.post('/group/logout',data={'csrf':'bad'}).status_code == 400
    assert state(client) == before
    assert client.post('/group/logout',data={'csrf':before['csrf']}).status_code == 303
    after = state(client)
    assert after['household_id'] == before['household_id'] and after['_permanent']
    assert after['csrf'] != before['csrf']
    assert not any(k in after for k in ('group_until','group_credential','admin_until','admin_credential'))
    assert backend.store.summaries([key],after['household_id'])[key]['people'] == 2
    assert client.get('/admin').location.endswith('/group/login')
    copied = app.test_client()
    copied.set_cookie(app.config['SESSION_COOKIE_NAME'],cookie)
    assert copied.get('/').status_code == 200
    signin(client)
    assert 'Fictional family' in client.get('/').text


def test_expiry_preserves_household_roster_responses(clock):
    _, client, backend = app_client()
    signin(client, '30_days')
    key = save_household(client, backend)
    before = state(client)
    household = backend.store.household(before['household_id'])
    clock[0] = before['group_until']
    assert client.get('/').status_code == 303
    signin(client)
    assert state(client)['household_id'] == before['household_id']
    assert backend.store.household(before['household_id']) == household
    assert backend.store.summaries([key],before['household_id'])[key]['people'] == 2


def test_password_rotation_and_tampered_cookie(clock):
    app, client, _ = app_client()
    signin(client, '30_days')
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME']).value
    altered = app.test_client()
    altered.set_cookie(app.config['SESSION_COOKIE_NAME'],cookie + 'tampered')
    assert altered.get('/').status_code == 303
    app.config['GROUP_ACCESS_PASSWORD_HASH'] = generate_password_hash('another-fictional-password',method='pbkdf2:sha256:1000')
    assert client.get('/').status_code == 303
    assert client.post('/attendance/unknown').status_code == 401


def test_activity_restart_empty_database_retains_original_deadline(clock, local_path):
    app, source, backend, publisher = seed(GROUP_ACCESS_PASSWORD_HASH=HASH,
        RSVP_DATABASE=str(local_path/'remember-old.sqlite3'))
    client = app.test_client()
    signin(client,'30_days')
    deadline = state(client)['group_until']
    identity = state(client)['household_id']
    clock[0] += 1000
    key = save_household(client,backend)
    assert state(client)['group_until'] == deadline
    profile = backend.store.household(identity)
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME']).value
    backend.store.connection.close()
    (local_path/'remember-old.sqlite3').unlink()
    clock[0] += 1000
    fresh, _, restored = make(source=source,SECRET_KEY=app.secret_key,GROUP_ACCESS_PASSWORD_HASH=HASH,
        RSVP_DATABASE=str(local_path/'remember-empty.sqlite3'))
    restored.publisher, restored.strict = publisher, True
    browser = fresh.test_client()
    browser.set_cookie(fresh.config['SESSION_COOKIE_NAME'],cookie)
    try:
        assert browser.get('/').status_code == 200
        assert state(browser)['group_until'] == deadline
        assert state(browser)['household_id'] == identity
        assert restored.store.household(identity) == profile
        assert restored.store.summaries([key],identity)[key]['people'] == 2
        clock[0] = deadline
        assert browser.get('/').status_code == 303
    finally:
        restored.store.connection.close()


def test_secure_cookie_health_and_auth_do_not_query_sheets(clock):
    with patch.object(SheetBackend,'request',side_effect=AssertionError('No live API allowed')):
        app = production()
        client = app.test_client()
        health = client.get('/health')
        assert health.json == {'status':'ok'} and 'Set-Cookie' not in health.headers
        response = client.get('/group/login')
        cookie = response.headers['Set-Cookie']
        assert all(flag in cookie for flag in ('Secure','HttpOnly','SameSite=Lax'))
        assert signin(client,'30_days').status_code == 303
        assert client.post('/group/logout',data={'csrf':state(client)['csrf']}).status_code == 303
