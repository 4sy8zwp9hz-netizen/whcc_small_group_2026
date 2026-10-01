from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from schedule import create_app
from schedule.data import (
    CHICAGO, FIELDS, CsvSource, DataError, GoogleSheetsSource,
    ScheduleCache, parse_meetings, select_meetings, table_rows,
)

NOW = datetime(2026, 10, 1, 12, tzinfo=CHICAGO)
MAPPING = dict(zip(FIELDS, FIELDS))


def row(date="2026-10-02", time="19:00", **kwargs):
    return {"date": date, "time": time, **kwargs}


def parse(rows):
    return parse_meetings(rows, MAPPING, "%Y-%m-%d", "%H:%M")


class FakeSource:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else [row()]
        self.calls = 0
        self.fail = False

    def read(self):
        self.calls += 1
        if self.fail:
            raise RuntimeError("SECRET MUST NOT REACH THE BROWSER")
        return self.rows


def app_for(source, **config):
    return create_app(
        {"TESTING": True, "DATA_SOURCE": "csv", "FIELD_MAPPING_JSON": "{}",
         "REQUIRED_ASSIGNMENTS": "discussion_leader,host,food,childcare",
         "DATE_FORMAT": "%Y-%m-%d", "TIME_FORMAT": "%H:%M", **config},
        source=source, now=lambda: NOW,
    )


def test_order_next_and_canceled():
    meetings = parse([
        row("2026-10-23"), row("2026-10-02", status="canceled"),
        row("2026-09-18"), row("2026-10-09"),
    ])
    upcoming, next_meeting = select_meetings(meetings, NOW)
    assert [m.starts_at.day for m in upcoming] == [2, 9, 23]
    assert next_meeting.starts_at.day == 9
    assert upcoming[0].canceled
    past, next_past = select_meetings(meetings, NOW, past=True)
    assert [m.starts_at.day for m in past] == [18]
    assert next_past is None


def test_exact_start_is_upcoming_and_past_is_chronological():
    meetings = parse([row("2026-09-25"), row("2026-10-01", "12:00"), row("2026-09-18")])
    upcoming, next_meeting = select_meetings(meetings, NOW)
    assert next_meeting == upcoming[0]
    past, _ = select_meetings(meetings, NOW, past=True)
    assert [m.starts_at.day for m in past] == [18, 25]


@pytest.mark.parametrize("status", ["canceled", "cancelled", " CANCELED "])
def test_cancellation_spellings(status):
    assert parse([row(status=status)])[0].canceled


def test_invalid_status_does_not_silently_schedule():
    with pytest.raises(DataError):
        parse([row(status="maybe")])


def test_blank_assignments_and_optional_fields():
    client = app_for(FakeSource()).test_client()
    html = client.get("/").get_data(as_text=True)
    assert "Needs assignment" in html
    assert "Good to know" not in html
    assert "Small group gathering" in html
    assert "Location to be confirmed" in html
    optional = app_for(FakeSource(), REQUIRED_ASSIGNMENTS="host").test_client()
    html = optional.get("/").get_data(as_text=True)
    assert "Discussion leader" not in html
    assert "Childcare" not in html
    assert "<dt>Host</dt>" in html


def test_canceled_assignments_do_not_request_volunteers():
    client = app_for(FakeSource([row(status="canceled", host="Alex")])).test_client()
    html = client.get("/").get_data(as_text=True)
    assert "Next gathering" not in html
    assert "All upcoming meetings are canceled" in html
    assert "Needs assignment" not in html
    assert "Host (previously planned)" in html


def test_past_route_and_empty_state():
    client = app_for(FakeSource([row("2026-09-18", topic="Earlier gathering")])).test_client()
    assert "No upcoming meetings" in client.get("/").get_data(as_text=True)
    html = client.get("/past").get_data(as_text=True)
    assert "Earlier gathering" in html
    assert "Next gathering" not in html


def test_cache_ttl_failure_retention_and_recovery():
    ticks = [0]
    source = FakeSource()
    cache = ScheduleCache(source, parse, monotonic=lambda: ticks[0], now=lambda: NOW)
    initial = cache.get()
    assert initial.last_success == NOW
    ticks[0] = 59
    assert cache.get() is initial
    assert source.calls == 1
    source.fail = True
    ticks[0] = 60
    failed = cache.get()
    assert failed.stale and failed.meetings == initial.meetings
    assert failed.last_success == initial.last_success
    ticks[0] = 61
    cache.get()
    assert source.calls == 2
    source.fail = False
    source.rows = [row("2026-10-16")]
    ticks[0] = 120
    recovered = cache.get()
    assert not recovered.stale
    assert recovered.meetings[0].starts_at.day == 16


def test_malformed_refresh_is_atomic():
    source = FakeSource()
    cache = ScheduleCache(source, parse, ttl=0)
    good = cache.get()
    source.rows = [row("2026-10-23"), row("not-a-date")]
    failed = cache.get()
    assert failed.meetings == good.meetings
    assert failed.stale


def test_initial_failure_returns_useful_503_and_throttles():
    source = FakeSource()
    source.fail = True
    client = app_for(source).test_client()
    response = client.get("/")
    assert response.status_code == 503
    html = response.get_data(as_text=True)
    assert "schedule is temporarily unavailable" in html
    assert "No successful refresh yet" in html
    assert "SECRET" not in html
    client.get("/")
    assert source.calls == 1


def test_stale_page_200_and_refresh_time_preserved():
    source = FakeSource()
    app = app_for(source)
    client = app.test_client()
    client.get("/")
    source.fail = True
    app.extensions["schedule_cache"].retry_at = float("-inf")
    response = client.get("/")
    assert response.status_code == 200
    assert "Showing the last successful schedule" in response.get_data(as_text=True)
    assert "Last successful refresh:" in response.get_data(as_text=True)


def test_custom_mapping_and_formats():
    mapping = {**MAPPING, "date": "Gathering", "time": "Start", "host": "Welcome"}
    rows = table_rows([["Gathering", "Start", "Welcome"], ["10/02/2026", "7:00 PM", "Alex"]])
    meetings = parse_meetings(rows, mapping, "%m/%d/%Y", "%I:%M %p")
    assert meetings[0].host == "Alex"
    assert meetings[0].starts_at.hour == 19


@pytest.mark.parametrize("table", [
    [], [["date", "date"]], [["date", ""]], [["date", "time"], ["x", "y", "extra"]],
])
def test_bad_table(table):
    with pytest.raises(DataError):
        table_rows(table)


def test_empty_success_is_distinct_from_failure():
    source = FakeSource(table_rows([["date", "time"]]))
    response = app_for(source).test_client().get("/")
    assert response.status_code == 200
    assert "No upcoming meetings" in response.get_data(as_text=True)


def test_missing_date_or_time_header():
    with pytest.raises(DataError):
        parse(table_rows([["wrong", "columns"]]))


@pytest.mark.parametrize("date,time", [("2026-03-08", "02:30"), ("2026-11-01", "01:30")])
def test_reject_dst_edge_times(date, time):
    with pytest.raises(DataError):
        parse([row(date, time)])


def test_central_timezone_changes_with_season():
    summer, winter = parse([row("2026-07-01"), row("2026-12-01")])
    assert summer.starts_at.strftime("%Z") == "CDT"
    assert winter.starts_at.strftime("%Z") == "CST"


def test_google_adapter_readonly_and_timeout():
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "values": [["date", "time"], ["2026-10-02", "19:00"]]
    }
    with patch("google.oauth2.service_account.Credentials.from_service_account_file") as auth:
        with patch("google.auth.transport.requests.AuthorizedSession") as transport:
            transport.return_value.__enter__.return_value = session
            rows = GoogleSheetsSource("example-id", "'Schedule'!A1:J500", "not-real.json").read()
    assert rows[0]["date"] == "2026-10-02"
    assert auth.call_args.kwargs["scopes"] == [
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]
    assert session.get.call_args.kwargs["timeout"] == 15
    assert "/values/" in session.get.call_args.args[0]
    session.get.return_value.raise_for_status.assert_called_once()


def test_html_escaped_and_security_headers():
    response = app_for(FakeSource([row(notes="<script>alert(1)</script>")])).test_client().get("/")
    assert b"<script>" not in response.data
    assert b"&lt;script&gt;" in response.data
    assert response.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_actual_sample_csv():
    from schedule import ROOT
    meetings = parse(CsvSource(ROOT / "data/sample.csv").read())
    assert len(meetings) == 7
    assert meetings[0].starts_at.day == 18
    assert sum(m.canceled for m in meetings) == 2
