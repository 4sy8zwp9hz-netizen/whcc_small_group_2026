import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template

from .data import (
    ASSIGNMENTS, CHICAGO, FIELDS, LABELS, CsvSource, GoogleSheetsSource,
    ScheduleCache, parse_meetings, select_meetings, table_rows,
)

ROOT = Path(__file__).resolve().parent.parent


def create_app(test_config=None, source=None, now=None):
    load_dotenv(ROOT / ".env", override=False)
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY") or None,
        RSVP_DATABASE=os.getenv("RSVP_DATABASE", "private/attendance.sqlite3"),
        RSVP_SECRET_FILE=os.getenv("RSVP_SECRET_FILE", "private/session.key"),
        SESSION_COOKIE_NAME=os.getenv("RSVP_COOKIE_NAME", "whcc_household"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(days=365),
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=16384,
        DATA_SOURCE=os.getenv("DATA_SOURCE", "csv"),
        SHEET_LAYOUT=os.getenv("SHEET_LAYOUT", "table"),
        CALENDAR_START_YEAR=int(os.getenv("CALENDAR_START_YEAR", "0")),
        CALENDAR_START_MONTH=int(os.getenv("CALENDAR_START_MONTH", "9")),
        CALENDAR_START_TIME=os.getenv("CALENDAR_START_TIME", ""),
        CALENDAR_DATE_COLUMN=os.getenv("CALENDAR_DATE_COLUMN", "A"),
        CALENDAR_EVENT_COLUMN=os.getenv("CALENDAR_EVENT_COLUMN", "D"),
        CALENDAR_END_MARKER=os.getenv("CALENDAR_END_MARKER", "Roles"),
        CALENDAR_TOPIC_LABELS_JSON=os.getenv("CALENDAR_TOPIC_LABELS_JSON", '["Sermon Series"]'),
        CALENDAR_CANCELED_DATES=os.getenv("CALENDAR_CANCELED_DATES", ""),
        CSV_PATH=os.getenv("CSV_PATH", "data/sample.csv"),
        CACHE_SECONDS=float(os.getenv("CACHE_SECONDS", "60")),
        FIELD_MAPPING_JSON=os.getenv("FIELD_MAPPING_JSON", "{}"),
        REQUIRED_ASSIGNMENTS=os.getenv(
            "REQUIRED_ASSIGNMENTS", ",".join(ASSIGNMENTS)
        ),
        DATE_FORMAT=os.getenv("DATE_FORMAT", "%Y-%m-%d"),
        TIME_FORMAT=os.getenv("TIME_FORMAT", "%H:%M"),
        GOOGLE_SHEET_ID=os.getenv("GOOGLE_SHEET_ID", ""),
        GOOGLE_SHEET_RANGE=os.getenv("GOOGLE_SHEET_RANGE", "'Schedule'!A1:J500"),
        GOOGLE_APPLICATION_CREDENTIALS=os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""),
    )
    if test_config:
        app.config.update(test_config)
    if app.testing and (not test_config or "RSVP_DATABASE" not in test_config):
        app.config["RSVP_DATABASE"] = ":memory:"
    mapping = dict(zip(FIELDS, FIELDS))
    overrides = json.loads(app.config["FIELD_MAPPING_JSON"])
    if not isinstance(overrides, dict) or any(
        key not in FIELDS or not isinstance(value, str) or not value.strip()
        for key, value in overrides.items()
    ):
        raise ValueError("FIELD_MAPPING_JSON must map known fields to nonempty headers.")
    mapping.update(overrides)
    required = {
        key.strip() for key in app.config["REQUIRED_ASSIGNMENTS"].split(",")
        if key.strip()
    }
    if not required.issubset(ASSIGNMENTS):
        raise ValueError("Unknown REQUIRED_ASSIGNMENTS field.")
    if not 1 <= app.config["CACHE_SECONDS"] <= 3600:
        raise ValueError("CACHE_SECONDS must be between 1 and 3600.")
    if app.config["DATA_SOURCE"] not in {"csv", "google"}:
        raise ValueError("DATA_SOURCE must be csv or google.")
    if app.config["SHEET_LAYOUT"] not in {"table", "calendar"}:
        raise ValueError("SHEET_LAYOUT must be table or calendar.")
    row_adapter = table_rows
    parser_mapping = mapping
    date_format, time_format = app.config["DATE_FORMAT"], app.config["TIME_FORMAT"]
    if app.config["SHEET_LAYOUT"] == "calendar":
        from .calendar import CalendarLayout
        topic_labels = json.loads(app.config["CALENDAR_TOPIC_LABELS_JSON"])
        if not isinstance(topic_labels, list):
            raise ValueError("CALENDAR_TOPIC_LABELS_JSON must be a JSON list.")
        row_adapter = CalendarLayout(
            mapping, app.config["CALENDAR_START_YEAR"], app.config["CALENDAR_START_MONTH"],
            app.config["CALENDAR_START_TIME"], app.config["CALENDAR_DATE_COLUMN"],
            app.config["CALENDAR_EVENT_COLUMN"], app.config["CALENDAR_END_MARKER"],
            topic_labels=topic_labels,
            canceled_dates=[day.strip() for day in
                            app.config["CALENDAR_CANCELED_DATES"].split(",") if day.strip()],
        )
        parser_mapping = dict(zip(FIELDS, FIELDS))
        date_format, time_format = "%Y-%m-%d", "%H:%M"
    if source is None:
        if app.config["DATA_SOURCE"] == "csv":
            source = CsvSource(ROOT / app.config["CSV_PATH"], row_adapter)
        else:
            source = GoogleSheetsSource(
                app.config["GOOGLE_SHEET_ID"], app.config["GOOGLE_SHEET_RANGE"],
                app.config["GOOGLE_APPLICATION_CREDENTIALS"], row_adapter,
            )
    now = now or (lambda: datetime.now(CHICAGO))
    cache = ScheduleCache(
        source,
        lambda rows: parse_meetings(
            rows, parser_mapping, date_format, time_format
        ),
        ttl=app.config["CACHE_SECONDS"], now=now,
    )
    app.extensions["schedule_cache"] = cache
    from .attendance import Attendance
    attendance_service = Attendance(app, ROOT, cache, now)
    app.extensions["attendance"] = attendance_service

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; img-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.template_filter("meeting_date")
    def meeting_date(value):
        return value.strftime("%A, %B ") + str(value.day) + value.strftime(", %Y")

    @app.template_filter("meeting_time")
    def meeting_time(value):
        return value.strftime("%I:%M %p %Z").lstrip("0")

    def schedule_page(past=False):
        snapshot = cache.get()
        meetings, next_meeting = select_meetings(snapshot.meetings or (), now(), past)
        week_start = now().date() - timedelta(days=now().weekday())
        this_week = [meeting for meeting in (snapshot.meetings or ())
                     if week_start <= meeting.starts_at.date() < week_start + timedelta(days=7)]
        featured = None
        featured_label = "Next gathering"
        if not past:
            if this_week:
                featured = next((m for m in this_week if m.starts_at >= now()), this_week[-1])
                featured_label = "This week"
            else:
                featured = next_meeting or (meetings[0] if meetings else None)
        remaining = [meeting for meeting in meetings if meeting is not featured]
        attendance_context = attendance_service.context(snapshot.meetings or (), snapshot)
        return render_template(
            "schedule.html", snapshot=snapshot, meetings=meetings,
            featured_meeting=featured, featured_label=featured_label,
            remaining_meetings=remaining, **attendance_context,
            next_meeting=next_meeting, past=past, labels=LABELS,
            required=required, sample=app.config["DATA_SOURCE"] == "csv",
        ), 503 if snapshot.meetings is None else 200

    @app.get("/")
    def upcoming():
        return schedule_page()

    @app.get("/past")
    def past():
        return schedule_page(past=True)

    return app
