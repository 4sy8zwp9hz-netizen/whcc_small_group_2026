"""Write only the explicitly configured app tab; original calendar stays read-only."""
import json
import re
import copy
import time
import hashlib
from urllib.parse import quote

from .backend import EDIT_FIELDS, encode, validate_values, digest
from .data import DataError

HEADERS = ["Meeting ID", "Date", "Time (Central)", "Location", "Topic", "Discussion leader",
           "Host", "Food", "Childcare", "Notes", "Status", "Special event",
           "People going", "Households going", "Households not going", "Sync conflicts",
           "App state (managed by app)"]


class SheetBackend:
    def __init__(self, spreadsheet_id, credentials_path, title, source_range):
        if not title or len(title) > 100 or any(c in title for c in "[]:*?/\\"):
            raise ValueError("Choose a valid backend tab name.")
        from .source_identity import source_title as parse_source_title
        source_title = parse_source_title(source_range)
        if title.casefold() == source_title.casefold():
            raise ValueError("The backend tab must differ from the original calendar.")
        self.spreadsheet_id, self.credentials_path, self.title = spreadsheet_id, credentials_path, title
        self._properties = None
        self._properties_until = 0
        self.receipts = {}
        self.base_url = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(spreadsheet_id, safe="")

    def request(self, method, suffix="", **kwargs):
        from google.auth.transport.requests import AuthorizedSession
        from .google_credentials import credentials_for
        credentials = credentials_for(self.credentials_path)
        with AuthorizedSession(credentials) as session:
            response = session.request(method, self.base_url + suffix, timeout=15, **kwargs)
            response.raise_for_status()
            return response.json()

    def sheets(self):
        return self.get(params={"fields": "sheets.properties"})["sheets"]

    def properties(self):
        if self._properties is not None and time.monotonic() < self._properties_until:
            return self._properties
        self._properties = next((s["properties"] for s in self.sheets()
                                 if s["properties"]["title"] == self.title), None)
        self._properties_until = time.monotonic() + 300
        return self._properties

    @staticmethod
    def retryable(exc):
        from requests.exceptions import ConnectionError, Timeout
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return isinstance(exc, (ConnectionError, Timeout, TimeoutError)) or status in {429, 500, 502, 503, 504}

    def get(self, suffix="", **kwargs):
        # One bounded retry for a safe GET. Never retry arbitrary validation/4xx errors.
        for attempt in range(2):
            try:
                return self.request("GET", suffix, **kwargs)
            except Exception as exc:
                if attempt or not self.retryable(exc):
                    raise
                time.sleep(0.2)

    @staticmethod
    def table(items):
        rows = [HEADERS]
        for item in items:
            record, replies = item["record"], item["responses"]
            values = record["values"]
            people = sum(len(r["attending"]) for r in replies)
            going = sum(bool(r["attending"]) for r in replies)
            rows.append([record["id"], *[values[k] for k in EDIT_FIELDS],
                         people, going, len(replies) - going,
                         ", ".join(record["conflicts"]), encode(item)])
        return rows

    @staticmethod
    def validate(items):
        if not isinstance(items, list):
            raise DataError("Invalid backend records.")
        seen = set()
        for item in items:
            record = item["record"]
            if not re.fullmatch(r"[a-f0-9]{32}", record["id"]) or record["id"] in seen:
                raise DataError("Backend meeting IDs must be unique.")
            seen.add(record["id"])
            validate_values(record["values"])
            validate_values(record["base"])
            if not isinstance(record["revision"], int) or record["revision"] < 1:
                raise DataError("Invalid backend revision.")
            if not isinstance(record["conflicts"], dict) or not set(record["conflicts"]).issubset({*EDIT_FIELDS, "_removed"}):
                raise DataError("Invalid backend conflicts.")
            reply_ids = set()
            profiles = item.get("households", [])
            if not isinstance(profiles, list) or len({profile["id"] for profile in profiles}) != len(profiles):
                raise DataError("Invalid or duplicate household profiles.")
            for reply in [*item["responses"], *[{**profile, "attending": []} for profile in profiles]]:
                if not re.fullmatch(r"[a-f0-9]{64}", reply["id"]) or (reply in item["responses"] and reply["id"] in reply_ids):
                    raise DataError("Backend household IDs must be unique.")
                if reply in item["responses"]:
                    reply_ids.add(reply["id"])
                if not isinstance(reply["name"], str) or not 1 <= len(reply["name"]) <= 60:
                    raise DataError("Invalid backend household.")
                members = reply["members"]
                if not isinstance(members, list) or not 1 <= len(members) <= 20:
                    raise DataError("Invalid backend members.")
                member_ids = [m["id"] for m in members]
                if len(set(member_ids)) != len(members) or not all(
                    re.fullmatch(r"[a-f0-9]{24}", m["id"]) and isinstance(m["name"], str)
                    and 1 <= len(m["name"]) <= 40 for m in members
                ) or not set(reply["attending"]).issubset(member_ids):
                    raise DataError("Invalid backend attendance.")

        from .state_patch import entities
        entities(items)

    def read(self):
        self.receipts = {}
        if not self.properties():
            return None
        target = "'" + self.title.replace("'", "''") + "'!A:Q"
        table = self.get("/values/" + quote(target, safe=""),
                             params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])
        if not table or table[0] != HEADERS:
            raise DataError("The backend tab has unexpected columns. Nothing was overwritten.")
        try:
            baseline = []
            events = []
            for row in table[1:]:
                if not any(str(v).strip() for v in row):
                    continue
                payload = json.loads(row[16])
                if isinstance(payload, dict) and payload.get("_event") in {1, 2}:
                    if row != self.event_row(payload):
                        raise DataError("A backend update was edited directly.")
                    events.append(payload)
                else:
                    if events:
                        raise DataError("Do not reorder the managed backend tab.")
                    baseline.append(payload)
            self.validate(baseline)
            if table[1:1 + len(baseline)] != self.table(baseline)[1:]:
                raise DataError("The managed backend tab was edited directly. No data was overwritten.")
            state, receipts = self.replay(baseline, events)
            self.receipts = receipts
            return state
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            if isinstance(exc, DataError):
                raise
            raise DataError("The backend tab contains invalid app records. Nothing was overwritten.") from None

    @staticmethod
    def event_row(event):
        return ["event:" + event["id"], "", "", "", "App update", "", "", "", "", "", "", "", "", "", "", "", encode(event)]

    @classmethod
    def replay(cls, baseline, events):
        state = copy.deepcopy(baseline)
        receipts = {}
        payloads = {}
        for event in events:
            identity = event["id"]
            if not re.fullmatch(r"[a-f0-9]{32}", identity):
                raise DataError("Invalid backend update identity.")
            if identity in receipts:
                if payloads[identity] != event:
                    raise DataError("Duplicate update identity has different contents.")
                continue
            version = event.get("_event", 1)
            if version == 1:
                cls.validate(event["changes"])
            elif version == 2:
                from .state_patch import apply
                candidate = apply(state, event["patch"])
                cls.validate(candidate)
            else:
                raise DataError("Unsupported backend event version.")
            if not isinstance(event["expected"], str) or not re.fullmatch(r"[a-f0-9]{64}", event["expected"]):
                raise DataError("Invalid backend update version.")
            accepted = event["expected"] == digest(state)
            if accepted and version == 2:
                state = candidate
            elif accepted:
                records = {item["record"]["id"]: item for item in state}
                records.update({item["record"]["id"]: item for item in event["changes"]})
                state = sorted(records.values(), key=lambda item: (item["record"]["values"]["date"],
                               item["record"]["values"]["time"], item["record"]["id"]))
                cls.validate(state)
            receipts[identity] = accepted
            payloads[identity] = event
        return state, receipts

    def commit(self, items, base):
        """Append a small mutation and return verified state; Sheets is not immutable."""
        from .state_patch import diff
        self.validate(items)
        event = {"_event": 2, "expected": digest(base), "patch": diff(base, items)}
        # Content-derived identity stays identical for a retry, even after restart.
        event["id"] = hashlib.sha256(encode(event).encode()).hexdigest()[:32]
        row = self.event_row(event)
        if len(row[16]) > 49000:
            raise DataError("This update exceeds the supported cell size. Reduce the batch or recover manually with all writers stopped.")
        target = "'" + self.title.replace("'", "''") + "'!A:Q"
        # At most two append attempts, with the exact same event ID and payload.
        # Unknown acceptance is checked before retrying; replay deduplicates late copies.
        for attempt in range(2):
            try:
                self.request("POST", "/values/" + quote(target, safe="") + ":append",
                             params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                             json={"values": [row]})
            except Exception as exc:
                if not self.retryable(exc):
                    raise
            try:
                state = self.read()
            except Exception as exc:
                if attempt or not self.retryable(exc):
                    raise
                time.sleep(0.2)
                continue
            if state is None:
                raise DataError("The backend tab is missing. Restore it before retrying.")
            receipt = self.receipts.get(event["id"])
            if receipt is True:
                return state
            if receipt is False:
                raise DataError("Another writer changed the backend. Reload before retrying.")
            if attempt:
                break
            # Even a successful append may not yet be visible. Retry only this same event.
            time.sleep(0.2)
        raise DataError("The update acknowledgment is unknown. Reload before retrying; it may already be saved.")

    def cells_request(self, sheet_id, items, old_rows=0):
        rows = self.table(items)
        if any(len(str(value)) > 49000 for row in rows for value in row):
            raise DataError("Attendance is too large for a sheet cell. Initialize smaller batches with all writers stopped.")
        cells = []
        for row in rows:
            values = []
            for value in row:
                kind = "boolValue" if isinstance(value, bool) else "numberValue" if isinstance(value, (int, float)) else "stringValue"
                values.append({"userEnteredValue": {kind: value}})
            cells.append({"values": values})
        return {"updateCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": max(len(rows), old_rows),
                      "startColumnIndex": 0, "endColumnIndex": len(HEADERS)},
            "rows": cells, "fields": "userEnteredValue"}}

    @staticmethod
    def format_requests(sheet_id, row_count):
        return [
            {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                                           "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
            {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 4, "endIndex": 5},
                                           "properties": {"pixelSize": 280}, "fields": "pixelSize"}},
            {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": row_count,
                                     "startColumnIndex": 1, "endColumnIndex": 16},
                            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                            "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment"}},
            {"autoResizeDimensions": {"dimensions": {"sheetId": sheet_id, "dimension": "ROWS",
                                                     "startIndex": 0, "endIndex": row_count}}},
        ]

    def create(self, items):
        self.validate(items)
        sheets = self.sheets()
        if any(s["properties"]["title"] == self.title for s in sheets):
            raise DataError("The backend tab already exists. It was not replaced.")
        sheet_id = max((s["properties"]["sheetId"] for s in sheets), default=0) + 1
        rows = max(1000, len(items) + 1)
        self.request("POST", ":batchUpdate", json={"requests": [
            {"addSheet": {"properties": {"sheetId": sheet_id, "title": self.title,
                                        "gridProperties": {"rowCount": rows, "columnCount": len(HEADERS),
                                                           "frozenRowCount": 1, "frozenColumnCount": 2}}}},
            self.cells_request(sheet_id, items),
            {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {"backgroundColor": {"red": .15, "green": .30, "blue": .25},
                                                          "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                                                          "wrapStrategy": "WRAP"}},
                            "fields": "userEnteredFormat"}},
            {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": len(HEADERS)},
                                           "properties": {"pixelSize": 180}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 16, "endIndex": 17},
                                           "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
        ] + self.format_requests(sheet_id, len(items) + 1)})
        return sheet_id

    def write(self, items):
        """Deliberately disabled: full-tab replacement can destroy append history."""
        raise DataError("Full-tab writes are disabled. Use append mutations; restore backups manually with all writers stopped.")
