"""Normalize a two-row school-year calendar into the standard schedule fields.

This module contains layout rules, not a real spreadsheet ID or group information.
"""
from collections import Counter
from datetime import date, datetime
import re

from .data import ASSIGNMENTS, FIELDS, DataError, HeaderRows


def column_index(column):
    if not isinstance(column, str) or not re.fullmatch(r"[A-Za-z]+", column):
        raise ValueError("Calendar columns must be letters such as A or D.")
    result = 0
    for char in column.upper():
        result = result * 26 + ord(char) - ord("A") + 1
    return result - 1


class CalendarLayout:
    def __init__(self, mapping, start_year, start_month, start_time,
                 date_column="A", event_column="D", end_marker="Roles",
                 topic_labels=("Sermon Series",), canceled_dates=(),
                 canceled_prefixes=("off ", "break ", "break!", "canceled", "cancelled")):
        if not 1900 <= start_year <= 9998 or not 1 <= start_month <= 12:
            raise ValueError("Calendar start year and month must be explicitly configured.")
        datetime.strptime(start_time, "%H:%M")
        self.mapping = mapping
        self.start_year = start_year
        self.start_month = start_month
        self.start_time = start_time
        self.date_column = column_index(date_column)
        self.event_column = column_index(event_column)
        self.end_marker = end_marker.strip().casefold()
        if not self.end_marker:
            raise ValueError("CALENDAR_END_MARKER must not be blank.")
        if not all(isinstance(label, str) and label.strip() for label in topic_labels):
            raise ValueError("Calendar topic labels must be nonempty strings.")
        self.topic_labels = {label.strip().casefold() for label in topic_labels}
        self.canceled_dates = {date.fromisoformat(value) for value in canceled_dates}
        self.canceled_prefixes = tuple(value.casefold() for value in canceled_prefixes)

    def meeting_date(self, text):
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                # Use a leap year to parse month/day before assigning the actual year.
                parsed = datetime.strptime(text + " 2000", fmt)
                year = self.start_year + (parsed.month < self.start_month)
                return date(year, parsed.month, parsed.day)
            except ValueError:
                continue
        raise DataError("Calendar date must be a month name and day.")

    def __call__(self, table):
        if not table:
            raise DataError("Calendar header row is missing.")
        headers = [str(value).strip() for value in table[0]]
        role_columns = {}
        for role in ASSIGNMENTS:
            header = self.mapping[role]
            if headers.count(header) != 1:
                raise DataError("Each mapped calendar assignment header must appear once.")
            role_columns[role] = headers.index(header)

        notes_header = self.mapping.get("notes", "notes")
        if headers.count(notes_header) > 1:
            raise DataError("Calendar notes header must be unique.")
        notes_column = headers.index(notes_header) if notes_header in headers else None

        groups = []
        current = None
        for row in table[1:]:
            cells = [str(value).strip() for value in row]
            if not any(cells):
                continue
            label = self.cell(cells, self.date_column)
            if label.casefold() == self.end_marker:
                break
            if label and label.casefold() not in self.topic_labels:
                day = self.meeting_date(label)
                current = {"day": day, "rows": [cells], "topics": []}
                groups.append(current)
            elif current is None:
                raise DataError("Calendar continuation row has no meeting date.")
            else:
                current["rows"].append(cells)
                if label:
                    current["topics"].append(label)

        normalized = []
        for group in groups:
            rows = group["rows"]
            roles = {
                role: self.combine(self.cell(row, index) for row in rows)
                for role, index in role_columns.items()
            }
            event = self.cell(rows[0], self.event_column)
            special = bool(event and not any(roles.values()) and not group["topics"])
            topic = event if special else self.combine(group["topics"])
            canceled = special and topic.casefold().startswith(self.canceled_prefixes)
            normalized.append({
                **dict.fromkeys(FIELDS, ""), **roles,
                "date": group["day"].isoformat(), "time": self.start_time,
                "topic": topic, "status": "canceled" if canceled else "scheduled",
                "notes": self.combine(self.cell(row, notes_column) for row in rows)
                         if notes_column is not None else "",
                "_special_event": special, "_date_conflict": False,
            })

        # Explicit leader-confirmed off dates win over duplicate regular entries.
        # Do not guess which entry is correct on other duplicated dates.
        for day in self.canceled_dates:
            matching = [row for row in normalized if row["date"] == day.isoformat()]
            if matching:
                chosen = next((row for row in matching if row["status"] == "canceled"), None)
                if chosen is None:
                    chosen = {
                        **dict.fromkeys(FIELDS, ""), "date": day.isoformat(),
                        "time": self.start_time, "topic": "Off week",
                        "status": "canceled", "_special_event": True,
                        "_date_conflict": False,
                    }
                normalized = [row for row in normalized if row["date"] != day.isoformat()]
                normalized.append(chosen)

        counts = Counter(row["date"] for row in normalized)
        for row in normalized:
            row["_date_conflict"] = counts[row["date"]] > 1
        return HeaderRows(sorted(normalized, key=lambda row: row["date"]), FIELDS)

    @staticmethod
    def cell(row, index):
        return row[index] if index < len(row) else ""

    @staticmethod
    def combine(values):
        return " / ".join(dict.fromkeys(value for value in values if value))
