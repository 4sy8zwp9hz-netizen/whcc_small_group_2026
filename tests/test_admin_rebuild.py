"""Backed-up explicit compaction; fictional data and no Google calls."""
import copy
import pytest
from schedule.backend import DataError
from schedule.recovery import BackendRecovery
from schedule.state_patch import entities
from test_admin_recovery import RecoveryTransport
from test_review_fixes import make_google
from test_backend_admin import login
from test_cloud_run import HASH, group_login


class RebuildTransport(RecoveryTransport):
    def __init__(self):
        super().__init__()
        self.replacements = []
        self.lose_rebuild_ack = False
        self.skip_replacement = False

    def request(self, method, suffix="", **kwargs):
        if method == "POST" and suffix == ":batchUpdate":
            mutation = kwargs["json"]["requests"][0].get("updateCells")
            if mutation and mutation["range"]["sheetId"] == 123:
                self.replacements.append(copy.deepcopy(mutation))
                if not self.skip_replacement:
                    self.rows = [[next(iter(cell["userEnteredValue"].values())) for cell in row["values"]]
                                 for row in mutation["rows"]]
                if self.lose_rebuild_ack:
                    raise TimeoutError("fictional unknown replacement acknowledgment")
                return {}
        return super().request(method, suffix, **kwargs)


def setup():
    transport = RebuildTransport()
    adapter = transport.adapter()
    return transport, adapter, BackendRecovery(adapter)


def test_rebuild_recovers_visible_damage_preserves_profiles_history_and_links():
    transport, adapter, recovery = setup()
    orphan = transport.rows.pop()
    base = adapter.read()
    desired = copy.deepcopy(base)
    desired[0]["record"]["values"]["notes"] = "Accepted fictional update"
    adapter.commit(desired, base)
    # Valid hidden event with damaged/missing visible projection, repeated event.
    transport.rows[-1][0] = ""
    transport.rows.append(copy.deepcopy(transport.rows[-1]))
    transport.rows[1][3] = "Visible-only fictional location"
    transport.rows.append(orphan)
    original = copy.deepcopy(transport.rows)
    plan = recovery.rebuild_preview()
    assert plan["meetings"] == plan["households"] == plan["responses"] == 1
    assert plan["events"] == 2 and plan["rows"] == [5]
    assert not transport.replacements and not transport.backup_calls
    recovery.rebuild(plan["token"])
    assert transport.backup == original
    assert adapter.read() == desired
    assert adapter.read()[0]["record"]["id"] == base[0]["record"]["id"]
    assert entities(adapter.read()) == entities(desired)
    assert len(transport.replacements) == 1
    assert transport.replacements[0]["range"]["endRowIndex"] == len(original)
    # A later normal append remains readable after compaction.
    again = copy.deepcopy(desired)
    again[0]["record"]["values"]["notes"] = "Later fictional update"
    assert adapter.commit(again, desired) == again
    # Cold instance, no SQLite cache, can recover the same durable state.
    app, _, backend = make_google()
    backend.publisher, backend.strict = transport.adapter(), True
    assert not backend.cache.get().stale
    assert backend.records()[0]["id"] == base[0]["record"]["id"]
    assert entities(backend.export()) == entities(again)


def test_rebuild_preserves_clear_response_and_stale_event_rejection():
    transport, adapter, recovery = setup()
    transport.rows.pop()
    base = adapter.read()
    desired = copy.deepcopy(base)
    desired[0]["responses"] = []
    adapter.commit(desired, base)
    with pytest.raises(DataError):
        stale = copy.deepcopy(base)
        stale[0]["record"]["values"]["notes"] = "Stale fictional edit"
        adapter.commit(stale, base)  # old predecessor, cannot resurrect attendance
    transport.rows[1][3] = "Visible damage"
    plan = recovery.rebuild_preview()
    assert plan["responses"] == 0 and plan["households"] == 1 and plan["rejected"] == 1
    recovery.rebuild(plan["token"])
    assert entities(adapter.read()) == entities(desired)


@pytest.mark.parametrize("case", ["json", "identified", "header", "duplicate", "reordered"])
def test_damaged_stored_data_refuses_without_writes(case):
    transport, adapter, recovery = setup()
    if case == "json": transport.rows[1][16] = "broken"
    elif case == "identified": transport.rows[-1][0] = "a"*32
    elif case == "header": transport.rows[0][0] = "bad"
    elif case == "duplicate": transport.rows.insert(2, copy.deepcopy(transport.rows[1]))
    else:
        transport.rows.pop()
        base = adapter.read()
        desired = copy.deepcopy(base)
        desired[0]["record"]["values"]["notes"] = "Fictional"
        adapter.commit(desired, base)
        transport.rows[1], transport.rows[2] = transport.rows[2], transport.rows[1]
    with pytest.raises(DataError): recovery.rebuild_preview()
    assert not transport.replacements and not transport.backup_calls


@pytest.mark.parametrize("case", ["stale", "backup_failure", "backup_mismatch", "overlap"])
def test_unverified_rebuild_never_replaces(case):
    transport, adapter, recovery = setup()
    plan = recovery.rebuild_preview()
    if case == "stale": transport.rows[-1][5] = "Another edit"
    elif case == "backup_failure": transport.fail_backup = True
    elif case == "backup_mismatch": transport.corrupt_backup = True
    else: transport.change_during_backup = True
    with pytest.raises((DataError, TimeoutError)): recovery.rebuild(plan["token"])
    assert not transport.replacements


@pytest.mark.parametrize("applied", [True, False])
def test_unknown_rebuild_ack_checked_without_retry(applied):
    transport, adapter, recovery = setup()
    plan = recovery.rebuild_preview()
    transport.lose_rebuild_ack = True
    transport.skip_replacement = not applied
    if applied: recovery.rebuild(plan["token"])
    else:
        with pytest.raises(DataError): recovery.rebuild(plan["token"])
    assert len(transport.replacements) == 1 and transport.backup


def test_admin_rebuild_auth_csrf_confirmation_and_refresh():
    transport, adapter, recovery = setup()
    app, _, backend = make_google(GROUP_ACCESS_PASSWORD_HASH=HASH)
    backend.publisher, backend.strict = adapter, True
    client = app.test_client()
    assert client.get("/admin/recovery/rebuild").location.endswith("/group/login")
    group_login(client)
    assert client.get("/admin/recovery/rebuild").location.endswith("/admin/login")
    token = login(client)
    assert client.get("/admin/recovery/rebuild").status_code == 200
    assert client.post("/admin/recovery/rebuild", data={"csrf":"bad"}).status_code == 400
    data = {"csrf": token, "token": recovery.rebuild_preview()["token"], "writers_stopped":"yes"}
    assert client.post("/admin/recovery/rebuild", data=data).status_code == 409
    assert not transport.replacements
    data["confirm_rebuild"] = "REBUILD"
    response = client.post("/admin/recovery/rebuild", data=data)
    assert response.status_code == 200 and "Backend rebuilt and verified" in response.text
    assert not backend.cache.get().stale and adapter.read()[0]["responses"]
