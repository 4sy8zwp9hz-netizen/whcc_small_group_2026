"""Observed header displacement, literal append placement and no-op regressions."""
import copy
import pytest
from schedule.backend import digest, DataError
from schedule.sheet_backend import HEADERS
from test_admin_rebuild import setup
from test_backend_admin import login
from test_review_fixes import make_google


def empty_event(base, identity="a"*32):
    return {"_event":2,"id":identity,"expected":digest(base),
            "patch":{"records":[],"profiles":[],"responses":[],"cleared":[]}}


@pytest.mark.parametrize("count",[1,3])
def test_rebuild_restores_header_displaced_by_empty_app_updates(count):
    transport, adapter, recovery = setup()
    transport.rows.pop()
    base=adapter.read()
    for n in range(count):
        transport.rows.insert(0,adapter.event_row(empty_event(base,str(n+1)*32)))
    old=copy.deepcopy(transport.rows)
    with pytest.raises(DataError,match="unexpected columns"):adapter.read()
    plan=recovery.rebuild_preview()
    assert plan["header_row"] == count+1 and plan["households"] == plan["responses"] == 1
    recovery.rebuild(plan["token"])
    assert transport.backup == old and transport.rows[0] == HEADERS
    assert adapter.read() == base
    desired=copy.deepcopy(base)
    desired[0]["record"]["values"]["notes"]="=Fictional literal text"
    assert adapter.commit(desired,base) == desired
    assert transport.rows[0] == HEADERS
    assert transport.posts[-1][0].startswith("event:") and len(transport.posts[-1]) == 17
    assert len(transport.replacements) == 1


@pytest.mark.parametrize("case",["meaningful","invalid","unknown"])
def test_rebuild_refuses_unrecognized_rows_above_header(case):
    transport, adapter, recovery=setup()
    event=empty_event([])
    if case=="meaningful":event["patch"]["records"]=[{"id":"fictional"}]
    elif case=="invalid":event["expected"]="invalid"
    if case=="unknown":row=["Unrecognized entry"]
    else:row=adapter.event_row(event)
    transport.rows.insert(0,row)
    with pytest.raises(DataError):recovery.rebuild_preview()
    assert not transport.backup_calls and not transport.replacements


def test_semantically_identical_state_skips_empty_events_and_refreshes_latest():
    transport, adapter, _=setup()
    transport.rows.pop()
    base=adapter.read()
    equivalent=copy.deepcopy(base)
    equivalent[0]["households"]=[]
    # Profiles also appear in responses; removing the redundant optional list is no change.
    assert adapter.commit(equivalent,base) == base and not transport.posts
    changed=copy.deepcopy(base)
    changed[0]["record"]["values"]["notes"]="Later fictional writer"
    adapter.commit(changed,base)
    before=len(transport.posts)
    assert adapter.commit(equivalent,base) == changed
    assert len(transport.posts)==before and transport.rows[0] == HEADERS


def test_displaced_header_route_rebuild_then_auto_refresh_keeps_row_one_header():
    transport, adapter, recovery=setup()
    transport.rows.pop()
    base=adapter.read()
    transport.rows.insert(0,adapter.event_row(empty_event(base)))
    app, _, backend=make_google()
    backend.publisher,backend.strict=adapter,True
    client=app.test_client()
    csrf=login(client)
    response=client.get("/admin/recovery/rebuild")
    assert response.status_code==200 and "displaced to row 2" in response.text
    token=recovery.rebuild_preview()["token"]
    response=client.post("/admin/recovery/rebuild",data={"csrf":csrf,"token":token,
                        "writers_stopped":"yes","confirm_rebuild":"REBUILD"})
    assert response.status_code==200 and "Backend rebuilt and verified" in response.text
    assert transport.rows[0]==HEADERS and not backend.cache.get().stale
    assert "You can edit" not in client.get("/admin").text  # normal source refresh succeeded
