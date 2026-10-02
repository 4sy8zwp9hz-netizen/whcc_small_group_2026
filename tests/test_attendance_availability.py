"""Calendar outages do not disable confirmed backend attendance."""
import copy
from unittest.mock import patch
import pytest
from test_cloud_run import seed
from test_backend_admin import make


def cold():
    _, source, _, publisher = seed()
    source.fail = True
    app, _, backend = make(source=source)
    backend.publisher, backend.strict = publisher, True
    return app, backend, publisher


def token(client):
    client.get("/")
    with client.session_transaction() as session:
        return session["csrf"]


def test_cold_calendar_outage_allows_durable_attendance_changes_and_clear():
    app, backend, publisher = cold()
    client = app.test_client()
    csrf = token(client)
    key = backend.records()[0]["id"]
    page = client.get("/").text
    assert "Attendance is available" in page and ">Submit</button>" in page
    assert "Attendance is closed for past meetings, or unavailable" not in page
    data = {"csrf":csrf,"action":"all","household":"Fictional family","people":"Alex, Sam"}
    response = client.post("/attendance/"+key,data=data,headers={"Accept":"application/json"})
    assert response.status_code == 200 and "Attendance saved" in response.json["message"]
    assert len(publisher.remote[0]["responses"][0]["attending"]) == 2
    member = publisher.remote[0]["responses"][0]["members"][0]["id"]
    for action, expected in [("custom",[member]),("none",[]),("clear",None)]:
        response = client.post("/attendance/"+key,data={"csrf":csrf,"action":action,"attending":member})
        assert response.status_code == 303
        replies = publisher.remote[0]["responses"]
        assert (replies[0]["attending"] if replies else None) == expected
    assert publisher.remote[0]["households"] and backend.cache.get().stale


@pytest.mark.parametrize("change",["cancel","past","conflict"])
def test_stale_calendar_response_rechecks_latest_backend_meeting(change):
    app, backend, publisher = cold()
    client=app.test_client()
    csrf=token(client)
    key=backend.records()[0]["id"]
    record=publisher.remote[0]["record"]
    if change == "cancel": record["values"]["status"]="canceled"
    elif change == "past": record["values"]["date"]="2026-09-01"
    else: record["conflicts"]={"date":"2026-10-03"}
    response=client.post("/attendance/"+key,data={"csrf":csrf,"action":"all","household":"Fictional","people":"Alex"})
    assert response.status_code == 409 and not publisher.remote[0]["responses"]


def test_backend_failure_still_refuses_and_never_claims_saved():
    app, backend, publisher = cold()
    client=app.test_client()
    csrf=token(client)
    key=backend.records()[0]["id"]
    with patch.object(publisher,"read",side_effect=ValueError("fictional corrupt backend")):
        response=client.post("/attendance/"+key,data={"csrf":csrf,"action":"all","household":"Fictional","people":"Alex"})
    assert response.status_code != 200 and not backend.attendance_available
    assert not publisher.remote[0]["responses"]
    assert ">Submit</button>" not in client.get("/").text


def test_failed_append_during_calendar_outage_rolls_back_response():
    app, backend, publisher = cold()
    client=app.test_client()
    csrf=token(client)
    key=backend.records()[0]["id"]
    with patch.object(publisher,"write",side_effect=TimeoutError):
        response=client.post("/attendance/"+key,data={"csrf":csrf,"action":"all","household":"Fictional","people":"Alex"})
    assert response.status_code == 503 and "not confirmed" in response.text
    assert not backend.export()[0]["responses"] and not publisher.remote[0]["responses"]


def test_admin_can_edit_verified_backend_during_calendar_outage_and_merge_later():
    from test_backend_admin import login, form
    app, backend, publisher = cold()
    client = app.test_client()
    csrf = login(client)
    client.get("/admin")
    record = backend.records()[0]
    url = "/admin/meetings/"+record["id"]
    page = client.get(url).text
    assert "You can edit the verified saved backend" in page
    assert 'disabled' not in page
    assert client.post(url,data=form(record,csrf,location="Fictional meeting hall")).status_code == 303
    assert publisher.remote[0]["record"]["values"]["location"] == "Fictional meeting hall"
    # Source recovery retains the override, then simultaneous field changes conflict.
    backend.source.fail = False
    backend.invalidate()
    assert not backend.cache.get().stale
    assert backend.records()[0]["values"]["location"] == "Fictional meeting hall"
    backend.source.rows[0]["location"] = "Different fictional hall"
    backend.invalidate()
    backend.cache.get()
    assert backend.records()[0]["conflicts"]["location"] == "Different fictional hall"


def test_admin_calendar_outage_still_rejects_stale_revision_and_failed_write():
    from test_backend_admin import login, form
    app, backend, publisher = cold()
    client=app.test_client()
    csrf=login(client)
    client.get("/admin")
    record=backend.records()[0]
    url="/admin/meetings/"+record["id"]
    publisher.remote[0]["record"]["revision"] += 1
    assert client.post(url,data=form(record,csrf,host="Changed")).status_code == 409
    current=copy.deepcopy(publisher.remote[0]["record"])
    with patch.object(publisher,"write",side_effect=TimeoutError):
        response=client.post(url,data=form(current,csrf,host="Not confirmed"))
    assert response.status_code == 409
    assert backend.records()[0] == current
    assert publisher.remote[0]["record"] == current
