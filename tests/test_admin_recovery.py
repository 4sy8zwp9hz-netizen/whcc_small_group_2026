"""Fictional recovery without live Google, full-tab replacement or history loss."""
import copy
from urllib.parse import unquote
import pytest
from schedule.backend import DataError
from schedule.recovery import BackendRecovery
from schedule.sheet_backend import SheetBackend
from test_review_fixes import Transport, legacy_payload, make_google
from test_backend_admin import login
from test_cloud_run import HASH, group_login


class RecoveryTransport(Transport):
    def __init__(self):
        super().__init__(legacy_payload())
        self.rows = copy.deepcopy(self.rows)
        self.rows.append(["", "2026-10-03", "", "", "", "Fictional accidental entry"])
        self.backup = None
        self.backup_title = None
        self.fail_backup = False
        self.corrupt_backup = False
        self.change_during_backup = False
        self.lose_clear_ack = False
        self.clear_calls = []
        self.backup_calls = []

    def request(self, method, suffix="", **kwargs):
        if method == "GET" and self.backup_title and self.backup_title in unquote(suffix):
            return {"values": copy.deepcopy(self.backup or [])}
        if method == "POST" and suffix == ":batchUpdate":
            self.backup_calls.append(copy.deepcopy(kwargs))
            request = kwargs['json']['requests'][0]
            if 'appendCells' in request:
                self.backup_calls.pop()
                return super().request(method, suffix, **kwargs)
            if 'addSheet' in request:
                self.backup_title = request['addSheet']['properties']['title']
                return {'replies':[{'addSheet':{'properties':{'sheetId':987}}}]}
            if self.fail_backup:
                raise TimeoutError('fictional backup failure')
            assert request['updateCells']['range']['sheetId'] == 987
            self.backup = [[next(iter(cell['userEnteredValue'].values())) for cell in row['values']]
                           for row in request['updateCells']['rows']]
            if self.corrupt_backup:
                self.backup[1][1] = 'changed'
            if self.change_during_backup:
                self.rows[-1][5] = 'Another fictional writer'
            return {}
        if method == 'POST' and suffix == '/values:batchClear':
            self.clear_calls.append(copy.deepcopy(kwargs))
            for target in kwargs['json']['ranges']:
                number = int(target.split('!A')[1].split(':')[0])
                self.rows[number-1] = []
            if self.lose_clear_ack:
                raise TimeoutError('fictional lost clear acknowledgment')
            return {}
        return super().request(method,suffix,**kwargs)


def setup():
    transport = RecoveryTransport()
    adapter = transport.adapter()
    return transport, adapter, BackendRecovery(adapter)


def test_preview_is_read_only_and_preserves_hidden_history_profiles():
    transport, adapter, recovery = setup()
    before = copy.deepcopy(transport.rows)
    plan = recovery.preview()
    assert plan['rows'] == [3] and plan['meetings'] == 1
    assert transport.rows == before and not transport.backup_calls and not transport.clear_calls
    title = recovery.repair(plan['token'])
    assert title.startswith('WHCC Recovery ')
    assert transport.backup == before
    assert transport.rows[:2] == before[:2]
    assert len(transport.clear_calls) == 1
    assert transport.clear_calls[0]['json']['ranges'] == ["'App Backend'!A3:Q3"]
    assert adapter.read() == legacy_payload()
    assert adapter.read()[0]['responses'] and adapter.read()[0]['households']


def test_preserves_version_two_event_and_member_ids():
    transport, adapter, recovery = setup()
    orphan = transport.rows.pop()
    base = adapter.read()
    desired = copy.deepcopy(base)
    desired[0]['record']['values']['notes'] = 'Fictional accepted event'
    adapter.commit(desired,base)
    transport.rows.append(orphan)
    before = copy.deepcopy(transport.rows)
    plan = recovery.preview()
    recovery.repair(plan['token'])
    assert transport.rows[:-1] == before[:-1]
    assert adapter.read() == desired


@pytest.mark.parametrize('case',['identified','malformed','edited','event','header'])
def test_refuses_other_damage_without_any_write(case):
    transport, _, recovery = setup()
    if case=='identified':transport.rows[-1][0]='a'*32
    elif case=='malformed':transport.rows[1][16]='broken private JSON'
    elif case=='edited':transport.rows[1][5]='Different visible leader'
    elif case=='event':transport.rows.insert(2,SheetBackend.event_row({'_event':2,'id':'a'*32,'expected':'b'*64,'patch':{}}))
    else:transport.rows[0][0]='wrong header'
    before=copy.deepcopy(transport.rows)
    with pytest.raises((DataError,ValueError,KeyError)):
        recovery.preview()
    assert transport.rows==before and not transport.backup_calls and not transport.clear_calls


@pytest.mark.parametrize('case',['stale','backup_failure','backup_mismatch','overlap'])
def test_stale_or_unverified_backup_never_clears(case):
    transport, _, recovery=setup()
    plan=recovery.preview()
    if case=='stale':transport.rows[-1][5]='New fictional edit'
    elif case=='backup_failure':transport.fail_backup=True
    elif case=='backup_mismatch':transport.corrupt_backup=True
    else:transport.change_during_backup=True
    with pytest.raises((DataError,TimeoutError)):
        recovery.repair(plan['token'])
    assert not transport.clear_calls
    assert transport.rows[-1][1]=='2026-10-03'


def test_unknown_clear_ack_is_verified_and_not_retried():
    transport, adapter, recovery=setup()
    transport.lose_clear_ack=True
    recovery.repair(recovery.preview()['token'])
    assert len(transport.clear_calls)==1 and adapter.read()==legacy_payload()


def test_literal_backup_never_interprets_formula_text():
    transport, _, recovery=setup()
    transport.rows[-1][5]='=IMPORTXML("fictional", "fictional")'
    recovery.repair(recovery.preview()['token'])
    cells=transport.backup_calls[1]['json']['requests'][0]['updateCells']['rows']
    assert cells[-1]['values'][5]['userEnteredValue']=={'stringValue':'=IMPORTXML("fictional", "fictional")'}


def test_admin_auth_csrf_preview_confirmation_and_success():
    transport, adapter, _=setup()
    app, _, backend=make_google(GROUP_ACCESS_PASSWORD_HASH=HASH)
    backend.publisher,backend.strict=adapter,True
    client=app.test_client()
    assert client.get('/admin/recovery').location.endswith('/group/login')
    group_login(client)
    assert client.get('/admin/recovery').location.endswith('/admin/login')
    csrf=login(client)
    assert client.post('/admin/recovery',data={'csrf':'bad'}).status_code==400
    response=client.get('/admin/recovery')
    assert response.status_code==200 and 'Back up and clear incomplete rows' in response.text
    plan=BackendRecovery(adapter).preview()
    assert client.post('/admin/recovery',data={'csrf':csrf,'token':plan['token']}).status_code==409
    assert not transport.clear_calls
    assert client.post('/admin/recovery',data={'csrf':csrf,'token':plan['token'],'writers_stopped':'yes'}).status_code==200
    assert adapter.read()[0]['responses'] and not backend.cache.get().stale


def test_cold_admin_remains_available_and_retry_does_not_publish_invalid_state():
    transport, adapter, _=setup()
    app, _, backend=make_google()
    backend.publisher,backend.strict=adapter,True
    client=app.test_client()
    csrf=login(client)
    response=client.get('/admin')
    assert response.status_code==200 and 'Schedule refresh failed' in response.text
    assert 'Check backend and recover incomplete rows' in response.text
    assert 'saved locally and waiting' not in response.text
    before=copy.deepcopy(transport.rows)
    assert client.post('/admin/sync',data={'csrf':csrf}).status_code==303
    assert transport.rows==before and not transport.posts
