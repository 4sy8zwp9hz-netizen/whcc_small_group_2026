from datetime import datetime

import pytest

from schedule import ROOT, create_app
from schedule.calendar import CalendarLayout
from schedule.data import CHICAGO, CsvSource, DataError, FIELDS, parse_meetings, select_meetings

MAPPING = dict(zip(FIELDS, FIELDS))
MAPPING.update(host="Host", food="Dinner", discussion_leader="Discussion", childcare="Childcare")
HEADERS = ["", "Host", "Dinner", "Worship", "Ice Breaker", "Prayer", "Discussion", "Childcare"]


def layout(**kwargs):
    return CalendarLayout(MAPPING, 2030, 9, "18:00", **kwargs)


def normalized(**kwargs):
    return CsvSource(ROOT / "tests/fixtures/calendar.csv", layout(**kwargs)).read()


def parse(rows):
    return parse_meetings(rows, dict(zip(FIELDS, FIELDS)), "%Y-%m-%d", "%H:%M")


def test_two_row_assignments_and_topic():
    meeting = parse(normalized())[0]
    assert meeting.host == "Example host"
    assert meeting.food == "Alex / Sam"
    assert meeting.discussion_leader == "Jordan / Morgan"
    assert meeting.childcare == "Taylor / Riley"
    assert meeting.topic == "Sermon Series"
    assert meeting.starts_at.hour == 18
    assert not meeting.special_event


def test_year_rollover_and_footer_exclusion():
    meetings = parse(normalized())
    assert len(meetings) == 6
    assert meetings[0].starts_at.year == 2030
    assert meetings[-1].starts_at.year == 2031
    assert all("role description" not in meeting.topic for meeting in meetings)


def test_event_and_off_week():
    meetings = parse(normalized())
    assert meetings[1].special_event and not meetings[1].canceled
    assert meetings[1].topic == "Autumn social"
    assert meetings[2].canceled
    assert meetings[2].topic == "Off week for a holiday"


def test_confirmed_off_date_suppresses_wrong_regular_entry():
    meetings = parse(normalized(canceled_dates=["2031-03-14"]))
    matches = [m for m in meetings if m.starts_at.date().isoformat() == "2031-03-14"]
    assert len(matches) == 1
    assert matches[0].canceled
    assert matches[0].host == ""
    assert not matches[0].date_conflict


def test_off_override_without_existing_off_entry():
    meetings = parse(normalized(canceled_dates=["2030-09-06"]))
    assert meetings[0].canceled and meetings[0].topic == "Off week"
    assert meetings[0].host == ""


def test_other_duplicate_dates_remain_visible_and_flagged():
    meetings = parse(normalized())
    duplicate = [m for m in meetings if m.starts_at.month == 3]
    assert len(duplicate) == 2
    assert all(m.date_conflict for m in duplicate)


def test_calendar_uses_same_next_meeting_rules():
    meetings = parse(normalized())
    _, next_meeting = select_meetings(meetings, datetime(2030, 9, 19, tzinfo=CHICAGO))
    assert next_meeting.starts_at.date().isoformat() == "2031-01-03"


def test_invalid_date_rejects_refresh_instead_of_becoming_a_topic():
    with pytest.raises(DataError):
        layout()([HEADERS, ["Septembr 6", "Example host"]])


def test_renamed_headers_and_configurable_date_column():
    mapping = {**MAPPING, "food": "Meal"}
    changed = [*HEADERS]
    changed[2] = "Meal"
    changed[0] = "Unused"
    changed.append("Date")
    result = CalendarLayout(mapping, 2030, 9, "18:00", date_column="I")(
        [changed, ["", "Example host", "Alex", "", "", "", "Jordan", "", "September 6"]]
    )
    assert result[0]["food"] == "Alex"


def test_missing_or_duplicate_mapped_header_fails():
    with pytest.raises(DataError):
        layout()([["", "Host", "Dinner"]])
    with pytest.raises(DataError):
        layout()([[*HEADERS, "Host"]])


def test_empty_header_only_calendar_is_valid():
    assert parse(layout()([HEADERS])) == ()


def test_leap_date_uses_configured_year():
    leap_layout = CalendarLayout(MAPPING, 2031, 9, "18:00")
    assert leap_layout.meeting_date("February 29").isoformat() == "2032-02-29"
    with pytest.raises(DataError):
        layout().meeting_date("February 29")


def test_trim_headers_ignore_unmapped_columns_and_deduplicate_names():
    headers = [*HEADERS, "Unrelated"]
    headers[2] = " Dinner "
    rows = layout()([
        headers,
        ["September 6", "Example host", "Alex", "", "", "", "Jordan", "", "DO NOT IMPORT"],
        ["Sermon Series", "", "Alex"],
    ])
    assert rows[0]["food"] == "Alex"
    assert "DO NOT IMPORT" not in str(rows)


def test_calendar_app_integration_and_special_event_blanks():
    import json
    app = create_app({
        "TESTING": True, "DATA_SOURCE": "csv", "SHEET_LAYOUT": "calendar",
        "CSV_PATH": "tests/fixtures/calendar.csv",
        "FIELD_MAPPING_JSON": json.dumps({key: MAPPING[key] for key in
                                         ("host", "food", "discussion_leader", "childcare")}),
        "CALENDAR_START_YEAR": 2030, "CALENDAR_START_MONTH": 9,
        "CALENDAR_START_TIME": "18:00", "CALENDAR_CANCELED_DATES": "",
    }, now=lambda: datetime(2030, 9, 12, tzinfo=CHICAGO))
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Autumn social" in html
    assert "6:00 PM CDT" in html
    assert "conflicting calendar information" in html
    featured = html.split('<article class="meeting featured')[1].split("</article>")[0]
    assert "Needs assignment" not in featured
    assert "Casey" not in html  # Unmapped Worship assignment.

def test_optional_notes_do_not_import_unmapped_private_column():
    mapping = {**MAPPING, "notes": "Event notes"}
    rows = CalendarLayout(mapping, 2030, 9, "18:00")([
        [*HEADERS, "Unrelated", "Event notes"],
        ["September 6", "Example host", "Alex", "", "", "", "Jordan", "",
         "DO NOT IMPORT", "Bring a notebook."],
        ["Sermon Series"],
    ])
    assert rows[0]["notes"] == "Bring a notebook."
    assert "DO NOT IMPORT" not in str(rows)


def test_google_adapter_passes_raw_calendar_to_layout():
    from unittest.mock import MagicMock, patch
    from schedule.data import GoogleSheetsSource
    session = MagicMock()
    session.get.return_value.json.return_value = {
        "values": [HEADERS, ["September 6", "Example host", "Alex"],
                   ["Sermon Series", "", "Sam"]]
    }
    with patch("google.oauth2.service_account.Credentials.from_service_account_file"):
        with patch("google.auth.transport.requests.AuthorizedSession") as transport:
            transport.return_value.__enter__.return_value = session
            rows = GoogleSheetsSource("example-id", "'Calendar'!A1:H200",
                                      "not-real.json", layout()).read()
    assert parse(rows)[0].food == "Alex / Sam"


def test_malformed_calendar_refresh_retains_last_success():
    from schedule.data import ScheduleCache

    class MutableCalendar:
        table = [HEADERS, ["September 6", "Example host"], ["Sermon Series"]]

        def read(self):
            return layout()(self.table)

    source = MutableCalendar()
    cache = ScheduleCache(source, parse, ttl=0)
    good = cache.get()
    assert good.meetings
    source.table = [HEADERS, ["Not a date", "Example host"]]
    failed = cache.get()
    assert failed.stale
    assert failed.meetings == good.meetings
    assert failed.last_success == good.last_success
