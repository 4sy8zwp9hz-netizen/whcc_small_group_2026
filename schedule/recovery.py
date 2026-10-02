"""Explicit admin quarantine for unidentified rows, never a full-tab reset."""
import copy
import secrets
from urllib.parse import quote
from .backend import DataError, digest
from .sheet_backend import HEADERS


class BackendRecovery:
    def __init__(self, publisher):
        self.publisher = publisher

    def raw(self, title=None):
        title = title or self.publisher.title
        target = "'" + title.replace("'", "''") + "'!A:Q"
        return self.publisher.get("/values/" + quote(target, safe=""),
                                  params={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])

    @staticmethod
    def normalized(table):
        rows = [row[:17] + [""] * (17 - len(row[:17])) for row in table]
        while rows and not any(value != "" for value in rows[-1]):
            rows.pop()
        return rows

    def preview(self):
        table = self.raw()
        if not table or table[0] != HEADERS:
            raise DataError("Backend columns do not match. This recovery cannot repair the header.")
        orphaned, kept = [], [table[0]]
        for number, row in enumerate(table[1:], 2):
            state = row[16] if len(row) > 16 else ""
            identity = row[0] if row else ""
            if any(value != "" for value in row) and not state:
                if identity:
                    raise DataError("Row %s has an identifier but no stored state. Automatic recovery is refused." % number)
                orphaned.append(number)
            else:
                kept.append(row)
        # Only missing-state, unidentified rows may be quarantined. Every other
        # record, baseline cell and event must pass the ordinary strict reader.
        state = self.publisher.decode_table(kept)
        if orphaned and not state:
            raise DataError("No valid meetings remain. Restore a complete backup instead.")
        return {"rows": orphaned, "meetings": len(state),
                "token": digest(self.normalized(table)), "table": table}

    def repair(self, token):
        plan = self.preview()
        if token != plan["token"]:
            raise DataError("The backend changed after preview. Review a new preview; nothing was cleared.")
        if not plan["rows"]:
            raise DataError("There are no incomplete rows to recover.")
        title = "WHCC Recovery " + secrets.token_hex(6)
        table = copy.deepcopy(plan["table"])
        # Preserve the full managed A:Q range as literal values in a new tab.
        cells = []
        for row in table:
            values = []
            for value in row:
                kind = "boolValue" if isinstance(value, bool) else "numberValue" if isinstance(value, (int, float)) else "stringValue"
                values.append({"userEnteredValue": {kind: value}})
            cells.append({"values": values})
        result = self.publisher.request("POST", ":batchUpdate", json={"requests": [
            {"addSheet": {"properties": {"title": title,
                "gridProperties": {"rowCount": max(1000, len(table)), "columnCount": 17}}}}
        ]})
        sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
        self.publisher.request("POST", ":batchUpdate", json={"requests": [{"updateCells": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": len(table),
                      "startColumnIndex": 0, "endColumnIndex": 17},
            "rows": cells, "fields": "userEnteredValue"}}]})
        if self.normalized(self.raw(title)) != self.normalized(table):
            raise DataError("The recovery backup could not be verified. Nothing was cleared.")
        # Stale-preview rejection narrows the race, but Sheets has no CAS. All
        # other writers must be stopped; this is deliberately explicit maintenance.
        current = self.preview()
        if current["token"] != token:
            raise DataError("The backend changed during backup. Backup retained; nothing was cleared.")
        quoted = "'" + self.publisher.title.replace("'", "''") + "'"
        try:
            self.publisher.request("POST", "/values:batchClear", json={
                "ranges": [quoted + "!A%s:Q%s" % (n, n) for n in plan["rows"]]})
        except Exception as exc:
            if not self.publisher.retryable(exc):
                raise
            # Unknown clear acknowledgment is inspected, never blindly retried.
        after = self.raw()
        for number in plan["rows"]:
            if number <= len(after) and any(value != "" for value in after[number - 1]):
                raise DataError("Recovery was not confirmed. Backup retained; inspect before retrying.")
        self.publisher.decode_table(after)
        return title
