"""Explicit verified-backup maintenance; normal runtime replacement stays disabled."""
import copy
import secrets
import json
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
        title = self.backup(plan["table"])
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

    def backup(self, table):
        title = "WHCC Recovery " + secrets.token_hex(6)
        table = copy.deepcopy(table)
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
            raise DataError("The recovery backup could not be verified. Nothing was replaced or cleared.")
        return title

    def rebuild_preview(self):
        """Recover validated hidden state; visible-only edits are archived, not imported."""
        table = self.raw()
        if not table or table[0] != HEADERS:
            raise DataError("Backend columns do not match. Restore the complete header before rebuilding.")
        baseline, events, archived = [], [], []
        try:
            for number, row in enumerate(table[1:], 2):
                if not any(value != "" for value in row):
                    continue
                stored = row[16] if len(row) > 16 else ""
                if not stored:
                    if row[0]:
                        raise DataError("Row %s has an identifier but no stored state. Rebuild cannot preserve it." % number)
                    archived.append(number)
                    continue
                payload = json.loads(stored)
                if isinstance(payload, dict) and payload.get("_event") in {1, 2}:
                    events.append(payload)
                else:
                    if events:
                        raise DataError("Stored meetings follow update events. Restore their original order before rebuilding.")
                    baseline.append(payload)
            self.publisher.validate(baseline)
            state, receipts = self.publisher.replay(baseline, events)
            self.publisher.validate(state)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            if isinstance(exc, DataError):
                raise
            raise DataError("Stored app data is damaged. Rebuild cannot safely preserve it.") from None
        if not state:
            raise DataError("No validated meetings remain. Rebuild was refused.")
        from .state_patch import entities
        records, profiles, responses = entities(state)
        # Preflight payload limits before making a backup or touching the backend.
        self.publisher.cells_request(0, state, len(table))
        return {"token": digest(self.normalized(table)), "table": table, "state": state,
                "meetings": len(records), "households": len(profiles), "responses": len(responses),
                "events": len(events), "rejected": sum(not value for value in receipts.values()),
                "rows": archived}

    def rebuild(self, token):
        plan = self.rebuild_preview()
        if token != plan["token"]:
            raise DataError("The backend changed after preview. Nothing was replaced.")
        properties = self.publisher.properties()
        if not properties:
            raise DataError("The backend tab is missing. Nothing was replaced.")
        title = self.backup(plan["table"])
        if digest(self.normalized(self.raw())) != token:
            raise DataError("The backend changed during backup. Backup retained; nothing was replaced.")
        # Explicit authenticated maintenance only. One bounded A:Q replacement
        # compacts the validated state; normal runtime write() remains disabled.
        mutation = self.publisher.cells_request(properties["sheetId"], plan["state"], len(plan["table"]))
        try:
            self.publisher.request("POST", ":batchUpdate", json={"requests": [mutation]})
        except Exception as exc:
            if not self.publisher.retryable(exc):
                raise
            # Unknown acknowledgment: read back once, never repeat replacement.
        restored = self.publisher.decode_table(self.raw())
        if digest(restored) != digest(plan["state"]):
            raise DataError("Rebuild is not confirmed. Backup retained; inspect before retrying.")
        return title
