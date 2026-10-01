"""Read-only sources, row normalization, and a process-local last-good cache."""
from __future__ import annotations

import csv
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import quote
from zoneinfo import ZoneInfo

CHICAGO = ZoneInfo("America/Chicago")
FIELDS = (
    "date", "time", "location", "topic", "discussion_leader",
    "host", "food", "childcare", "notes", "status",
)
ASSIGNMENTS = ("discussion_leader", "host", "food", "childcare")
LABELS = {
    "discussion_leader": "Discussion leader", "host": "Host",
    "food": "Food", "childcare": "Childcare",
}


class DataError(ValueError):
    pass


class Source(Protocol):
    def read(self) -> list[dict[str, str]]: ...


def table_rows(table: list[list[str]]) -> list[dict[str, str]]:
    if not table:
        raise DataError("A header row is required.")
    headers = [str(value).strip() for value in table[0]]
    if any(not header for header in headers) or len(set(headers)) != len(headers):
        raise DataError("Headers must be nonempty and unique.")
    rows = []
    for row in table[1:]:
        if not any(str(value).strip() for value in row):
            continue
        if len(row) > len(headers):
            raise DataError("A row has more values than headers.")
        rows.append(dict(zip(headers, [str(v).strip() for v in row] +
                             [""] * (len(headers) - len(row)))))
    # Keep headers even when there are no meetings, for schema validation.
    return HeaderRows(rows, headers)


class HeaderRows(list):
    def __init__(self, rows, headers):
        super().__init__(rows)
        self.headers = headers


class CsvSource:
    def __init__(self, path: Path, row_adapter=table_rows):
        self.path = path
        self.row_adapter = row_adapter

    def read(self):
        with self.path.open(encoding="utf-8-sig", newline="") as stream:
            return self.row_adapter(list(csv.reader(stream)))


class GoogleSheetsSource:
    """Only a Sheets values GET with the spreadsheets.readonly scope."""

    def __init__(self, spreadsheet_id: str, sheet_range: str, credentials_path: str,
                 row_adapter=table_rows):
        self.spreadsheet_id = spreadsheet_id
        self.sheet_range = sheet_range
        self.credentials_path = credentials_path
        self.row_adapter = row_adapter

    def read(self):
        # Lazy import/authentication: CSV mode never needs Google credentials.
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        if not all((self.spreadsheet_id, self.sheet_range, self.credentials_path)):
            raise DataError("Google Sheets configuration is incomplete.")
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        url = (
            "https://sheets.googleapis.com/v4/spreadsheets/"
            + quote(self.spreadsheet_id, safe="")
            + "/values/" + quote(self.sheet_range, safe="")
        )
        with AuthorizedSession(credentials) as session:
            response = session.get(
                url, params={"valueRenderOption": "FORMATTED_VALUE"}, timeout=15
            )
            response.raise_for_status()
            return self.row_adapter(response.json().get("values", []))


@dataclass(frozen=True)
class Meeting:
    starts_at: datetime
    location: str
    topic: str
    discussion_leader: str
    host: str
    food: str
    childcare: str
    notes: str
    canceled: bool
    special_event: bool = False
    date_conflict: bool = False


def parse_meetings(rows, mapping, date_format, time_format) -> tuple[Meeting, ...]:
    headers = set(getattr(rows, "headers", rows[0].keys() if rows else []))
    if not {mapping["date"], mapping["time"]}.issubset(headers):
        raise DataError("Date and time columns are required.")
    meetings = []
    for row in rows:
        values = {field: str(row.get(mapping[field], "")).strip() for field in FIELDS}
        status = values["status"].lower()
        if status not in {"", "scheduled", "canceled", "cancelled"}:
            raise DataError("Status must be scheduled, canceled, or blank.")
        naive = datetime.strptime(
            values["date"] + " " + values["time"], date_format + " " + time_format
        )
        starts_at = naive.replace(tzinfo=CHICAGO)
        # Reject nonexistent spring-forward and ambiguous fall-back wall times.
        if starts_at.astimezone(timezone.utc).astimezone(CHICAGO).replace(tzinfo=None) != naive:
            raise DataError("Meeting time does not exist because of daylight saving time.")
        if starts_at.utcoffset() != naive.replace(tzinfo=CHICAGO, fold=1).utcoffset():
            raise DataError("Meeting time is ambiguous because of daylight saving time.")
        meetings.append(Meeting(
            starts_at=starts_at,
            canceled=status in {"canceled", "cancelled"},
            special_event=row.get("_special_event") is True,
            date_conflict=row.get("_date_conflict") is True,
            **{key: values[key] for key in FIELDS if key not in {"date", "time", "status"}},
        ))
    return tuple(sorted(meetings, key=lambda meeting: meeting.starts_at))


@dataclass(frozen=True)
class Snapshot:
    meetings: tuple[Meeting, ...] | None
    last_success: datetime | None
    stale: bool


class ScheduleCache:
    """Cache successful reads; also throttle retries after failures for the TTL."""

    def __init__(self, source: Source, parser: Callable, ttl=60,
                 monotonic=time.monotonic, now=lambda: datetime.now(CHICAGO)):
        self.source = source
        self.parser = parser
        self.ttl = ttl
        self.monotonic = monotonic
        self.now = now
        self.lock = threading.Lock()
        self.retry_at = float("-inf")
        self.snapshot = Snapshot(None, None, False)

    def get(self) -> Snapshot:
        with self.lock:
            if self.monotonic() < self.retry_at:
                return self.snapshot
            try:
                meetings = self.parser(self.source.read())
                self.snapshot = Snapshot(meetings, self.now(), False)
            except Exception as exc:
                # Do not log sheet contents, credential paths, IDs, or exception text.
                logging.getLogger(__name__).warning(
                    "Schedule refresh failed (%s)", type(exc).__name__
                )
                self.snapshot = Snapshot(
                    self.snapshot.meetings, self.snapshot.last_success, True
                )
            self.retry_at = self.monotonic() + self.ttl
            return self.snapshot


def select_meetings(meetings, now, past=False):
    ordered = sorted(meetings, key=lambda meeting: meeting.starts_at)
    visible = [meeting for meeting in ordered
               if (meeting.starts_at < now if past else meeting.starts_at >= now)]
    next_meeting = next((meeting for meeting in visible if not meeting.canceled), None)
    return visible, None if past else next_meeting
