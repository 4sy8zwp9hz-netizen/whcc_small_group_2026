"""Write only the explicitly configured app tab; original calendar stays read-only."""
import json
import re
import uuid
import copy
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
        source_title = source_range.split("!")[0].strip("'").replace("''", "'")
        if title.casefold() == source_title.casefold():
            raise ValueError("The backend tab must differ from the original calendar.")
        self.spreadsheet_id, self.credentials_path, self.title = spreadsheet_id, credentials_path, title
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
        return self.request("GET", params={"fields": "sheets.properties"})["sheets"]

    def properties(self):
        return next((s["properties"] for s in self.sheets() if s["properties"]["title"] == self.title), None)

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
            if not isinstance(profiles, list):
                raise DataError("Invalid household profiles.")
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

    def read(self):
        if not self.properties():
            return None
        target = "'" + self.title.replace("'", "''") + "'!A:Q"
        table = self.request("GET", "/values/" + quote(target, safe=""),
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
                if isinstance(payload, dict) and payload.get("_event") == 1:
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
            cls.validate(event["changes"])
            if not isinstance(event["expected"], str) or not re.fullmatch(r"[a-f0-9]{64}", event["expected"]):
                raise DataError("Invalid backend update version.")
            accepted = event["expected"] == digest(state)
            if accepted:
                records = {item["record"]["id"]: item for item in state}
                records.update({item["record"]["id"]: item for item in event["changes"]})
                state = sorted(records.values(), key=lambda item: (item["record"]["values"]["date"],
                               item["record"]["values"]["time"], item["record"]["id"]))
                cls.validate(state)
            receipts[identity] = accepted
            payloads[identity] = event
        return state, receipts

    def commit(self, items, base):
        """Append one optimistic event; never rewrite accepted history."""
        self.validate(items)
        old = {item["record"]["id"]: item for item in base}
        if set(old) - {item["record"]["id"] for item in items}:
            raise DataError("Deleting backend records is not supported.")
        changes = [item for item in items if old.get(item["record"]["id"]) != item]
        event = {"_event": 1, "id": uuid.uuid4().hex, "expected": digest(base), "changes": changes}
        row = self.event_row(event)
        if len(row[16]) > 49000:
            raise DataError("This update exceeds the Sheets cell limit. Split it into smaller changes.")
        target = "'" + self.title.replace("'", "''") + "'!A:Q"
        try:
            self.request("POST", "/values/" + quote(target, safe="") + ":append",
                         params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                         json={"values": [row]})
        except Exception:
            # A timed-out append may still have persisted; inspect its receipt once.
            pass
        self.read()
        if not self.receipts.get(event["id"]):
            raise DataError("The update was not confirmed or another writer changed the backend. Reload before retrying.")

    def cells_request(self, sheet_id, items, old_rows=0):
        rows = self.table(items)
        if any(len(str(value)) > 49000 for row in rows for value in row):
            raise DataError("Attendance is too large for a sheet cell. Use a database before adding more households.")
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
        self.validate(items)
        properties = self.properties()
        if properties is None:
            raise DataError("The backend tab is missing.")
        needed = len(items) + 1
        requests = []
        if needed > properties["gridProperties"]["rowCount"]:
            requests.append({"appendDimension": {"sheetId": properties["sheetId"], "dimension": "ROWS",
                                                 "length": needed - properties["gridProperties"]["rowCount"]}})
        requests.append(self.cells_request(properties["sheetId"], items,
                                           min(properties["gridProperties"]["rowCount"], max(needed, 1000))))
        self.request("POST", ":batchUpdate", json={"requests": requests})
