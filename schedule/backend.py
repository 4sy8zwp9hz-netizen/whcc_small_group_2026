"""Durable effective schedule, three-way calendar merge, and sheet publication."""
import copy
import hashlib
import json
import time

from .data import FIELDS, DataError, HeaderRows, Snapshot, parse_meetings

EDIT_FIELDS = (*FIELDS, "special_event")
MAPPING = dict(zip(FIELDS, FIELDS))


def encode(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def meeting_values(meeting):
    return {
        **{field: getattr(meeting, field) for field in FIELDS
           if field not in {"date", "time", "status"}},
        "date": meeting.starts_at.date().isoformat(),
        "time": meeting.starts_at.strftime("%H:%M"),
        "status": "canceled" if meeting.canceled else "scheduled",
        "special_event": meeting.special_event,
    }


def validate_values(values):
    if set(values) != set(EDIT_FIELDS):
        raise DataError("The schedule fields do not match the expected format.")
    for field in FIELDS:
        if not isinstance(values[field], str) or len(values[field]) > (2000 if field == "notes" else 300):
            raise DataError("A schedule field is too long or invalid.")
    if not isinstance(values["special_event"], bool):
        raise DataError("Choose a valid meeting type.")
    parse_meetings([values], MAPPING, "%Y-%m-%d", "%H:%M")


def merge_record(record, incoming):
    """Retain app overrides; flag simultaneous edits to the same field."""
    result = copy.deepcopy(record)
    conflicts = {}
    if incoming is None:
        if not result.get("detached"):
            conflicts["_removed"] = "This date was removed or moved in the original calendar."
    else:
        result["detached"] = False
        for field in EDIT_FIELDS:
            base, local, remote = result["base"][field], result["values"][field], incoming[field]
            if remote == base:
                continue
            if local == base or local == remote:
                result["values"][field] = remote
                result["base"][field] = remote
            else:
                conflicts[field] = remote
    result["conflicts"] = conflicts
    if result != record:
        result["revision"] += 1
    return result


class Backend:
    def __init__(self, app, cache, attendance, publisher=None):
        self.app, self.cache, self.attendance = app, cache, attendance
        self.store = attendance.store
        self.source, self.parser = cache.source, cache.parser
        self.publisher = publisher
        self.strict = app.config.get("STRICT_DURABILITY", False)
        self.retry_at = 0
        self.sync_error = ""
        self.scope = hashlib.sha256(attendance.namespace.encode()).hexdigest()
        with self.store.lock, self.store.connection:
            self.store.connection.executescript("""
                CREATE TABLE IF NOT EXISTS app_schedule (
                    scope TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(scope,id));
                CREATE TABLE IF NOT EXISTS app_metadata (
                    scope TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                    PRIMARY KEY(scope,key));
            """)
        # Move the old quoted-name scope without changing IDs or queued SQLite state.
        if app.config["DATA_SOURCE"] == "google" and not self.records():
            from .source_identity import legacy_namespaces
            aliases = {hashlib.sha256(n.encode()).hexdigest() for n in legacy_namespaces(
                app.config["GOOGLE_SHEET_ID"], app.config["GOOGLE_SHEET_RANGE"])} - {self.scope}
            found = [scope for scope in aliases if self.store.connection.execute(
                "SELECT 1 FROM app_schedule WHERE scope=? LIMIT 1", (scope,)).fetchone()]
            if len(found) > 1:
                raise DataError("Multiple old source scopes exist. Preserve the cache and reconcile them before migration.")
            if found:
                with self.store.lock, self.store.connection:
                    self.store.connection.execute("UPDATE app_schedule SET scope=? WHERE scope=?", (self.scope, found[0]))
                    for row in self.store.connection.execute("SELECT key,value FROM app_metadata WHERE scope=?", (found[0],)).fetchall():
                        self.set_meta(row["key"], row["value"])
                    self.store.connection.execute("DELETE FROM app_metadata WHERE scope=?", (found[0],))
        cache.source = self
        cache.parser = lambda rows: parse_meetings(rows, MAPPING, "%Y-%m-%d", "%H:%M")
        if self.records():
            cache.snapshot = Snapshot(cache.parser(self.rows()), None, True)

    def meta(self, key, default=""):
        row = self.store.connection.execute(
            "SELECT value FROM app_metadata WHERE scope=? AND key=?", (self.scope, key)).fetchone()
        return row[0] if row else default

    def set_meta(self, key, value):
        self.store.connection.execute(
            "INSERT INTO app_metadata VALUES(?,?,?) ON CONFLICT(scope,key) DO UPDATE SET value=excluded.value",
            (self.scope, key, value))

    def records(self):
        with self.store.lock:
            return sorted(
                [json.loads(row[0]) for row in self.store.connection.execute(
                    "SELECT body FROM app_schedule WHERE scope=?", (self.scope,))],
                key=lambda r: (r["values"]["date"], r["values"]["time"], r["id"]))

    def put(self, record):
        self.store.connection.execute(
            "INSERT INTO app_schedule VALUES(?,?,?) ON CONFLICT(scope,id) DO UPDATE SET body=excluded.body",
            (self.scope, record["id"], encode(record)))

    def read(self):
        base = None
        if self.strict:
            with self.store.lock, self.store.connection:
                base = self.refresh_remote()
                self.cache.snapshot = Snapshot(self.cache.parser(self.rows()), self.attendance.now(), True)
        elif self.publisher and not self.records():
            with self.store.lock, self.store.connection:
                self.restore_if_available()
        old_records = self.records()
        meetings = self.parser(self.source.read())
        incoming = {}
        for meeting in meetings:
            matches = [record for record in old_records
                       if record["source_date"] == meeting.starts_at.date().isoformat()]
            if len(matches) > 1:
                raise DataError("Existing backend dates are ambiguous. Reconcile duplicate records before syncing.")
            key = matches[0]["id"] if matches else self.attendance.key(meeting)
            if key in incoming or meeting.date_conflict:
                raise DataError("Resolve duplicate dates in the original calendar before syncing.")
            incoming[key] = meeting_values(meeting)
        with self.store.lock, self.store.connection:
            if not self.records() and self.publisher:
                self.restore_if_available()
            old = {r["id"]: r for r in self.records()}
            for key, values in incoming.items():
                if key not in old:
                    self.put({"id": key, "source_date": values["date"], "values": values,
                              "base": copy.deepcopy(values), "conflicts": {}, "revision": 1,
                              "detached": False})
                else:
                    self.put(merge_record(old[key], values))
            for key in old.keys() - incoming.keys():
                if old[key]["source_date"]:
                    self.put(merge_record(old[key], None))
        if not self.publish(force=self.strict, base=base) and self.strict:
            with self.store.lock, self.store.connection:
                self.refresh_remote()
            raise DataError("The schedule refresh could not be confirmed in Sheets.")
        return self.rows()

    def rows(self):
        records = self.records()
        dates = [r["values"]["date"] for r in records]
        return HeaderRows([
            {**r["values"], "_record_id": r["id"],
             "_special_event": r["values"]["special_event"],
             "_date_conflict": bool(r["conflicts"]) or dates.count(r["values"]["date"]) > 1}
            for r in records], FIELDS)

    def edit(self, key, revision, values, resolutions):
        validate_values(values)
        with self.store.lock, self.store.connection:
            backup = self.refresh_remote() if self.strict else None
            record = next((r for r in self.records() if r["id"] == key), None)
            if record is None or str(record["revision"]) != str(revision):
                raise DataError("This meeting changed while you were editing. Reload and review the latest values.")
            for field, incoming in record["conflicts"].items():
                choice = resolutions.get(field)
                if field == "_removed":
                    if choice not in {"keep", "cancel"}:
                        raise DataError("Choose whether to keep or cancel the removed calendar entry.")
                    record["detached"] = True
                    if choice == "cancel":
                        values["status"] = "canceled"
                else:
                    if choice not in {"app", "calendar"}:
                        raise DataError("Choose a value for every conflicting field.")
                    if choice == "calendar":
                        values[field] = incoming
                    record["base"][field] = incoming
            validate_values(values)
            if any(r["id"] != key and r["values"]["date"] == values["date"] for r in self.records()):
                raise DataError("Another meeting already uses that date.")
            record["values"], record["conflicts"] = values, {}
            record["revision"] += 1
            self.put(record)
            if self.strict and not self.publish(force=True, base=backup):
                self.restore(backup, replace=True)
                raise DataError("The edit was not confirmed in Sheets. Reload before retrying.")
        self.invalidate()
        if not self.strict:
            self.publish(force=True)

    def invalidate(self):
        # Call outside the attendance lock to maintain cache -> store lock ordering.
        with self.cache.lock:
            self.cache.retry_at = float("-inf")

    def export(self):
        records = self.records()
        result = []
        for record in records:
            replies = []
            for row in self.store.connection.execute("""
                SELECT r.household_id,r.attending,r.updated_at,h.name,h.members
                FROM responses r JOIN households h ON h.id=r.household_id
                WHERE r.meeting_id=? ORDER BY r.household_id
            """, (record["id"],)):
                identity = row["household_id"]
                public_id = identity[7:] if identity.startswith("import:") else hashlib.sha256(identity.encode()).hexdigest()
                replies.append({"id": public_id, "name": row["name"], "members": json.loads(row["members"]),
                                "attending": json.loads(row["attending"]), "updated_at": row["updated_at"]})
            result.append({"record": record, "responses": sorted(replies, key=lambda r: r["id"])})
        if result:
            households = []
            for row in self.store.connection.execute("SELECT id,name,members FROM households ORDER BY id"):
                identity = row["id"]
                public_id = identity[7:] if identity.startswith("import:") else hashlib.sha256(identity.encode()).hexdigest()
                households.append({"id": public_id, "name": row["name"], "members": json.loads(row["members"])})
            result[0]["households"] = sorted(households, key=lambda h: h["id"])
        return result

    def restore_if_available(self):
        remote = self.publisher.read()
        if remote is None:
            return
        self.restore(remote)

    def refresh_remote(self):
        remote = self.publisher.read()
        if remote is None:
            raise DataError("Create the App Backend tab before starting production.")
        self.restore(remote, replace=True)
        return remote

    def restore(self, remote, replace=False):
        self.publisher.validate(remote)
        if replace:
            self.store.connection.execute("DELETE FROM responses")
            self.store.connection.execute("DELETE FROM households")
            self.store.connection.execute("DELETE FROM app_schedule WHERE scope=?", (self.scope,))
        for item in remote:
            record = item["record"]
            self.put(record)
            roster = item.get("households", [])
            for household in roster:
                self.store.connection.execute("INSERT OR IGNORE INTO households VALUES(?,?,?)",
                                              ("import:" + household["id"], household["name"], encode(household["members"])))
            for reply in item["responses"]:
                visitor = "import:" + reply["id"]
                existing = self.store.connection.execute("SELECT members FROM households WHERE id=?", (visitor,)).fetchone()
                if existing and json.loads(existing[0]) != reply["members"]:
                    raise DataError("Backend household roster is inconsistent.")
                self.store.connection.execute("INSERT OR IGNORE INTO households VALUES(?,?,?)",
                                              (visitor, reply["name"], encode(reply["members"])))
                self.store.connection.execute("INSERT OR IGNORE INTO responses VALUES(?,?,?,?)",
                                              (record["id"], visitor, encode(reply["attending"]), reply["updated_at"]))
        self.set_meta("published_hash", digest(remote))
        self.set_meta("last_sync", self.attendance.now().isoformat())

    def publish(self, force=False, base=None):
        if not self.publisher:
            return True
        if not force and time.monotonic() < self.retry_at:
            return not self.sync_error
        with self.store.lock:
            try:
                desired = self.export()
                expected = self.meta("published_hash")
                remote = base if base is not None else self.publisher.read()
                if remote is None:
                    raise DataError("Create the App Backend tab using the setup command.")
                actual = digest(remote)
                wanted = digest(desired)
                if actual != wanted:
                    if not expected or actual != expected:
                        raise DataError("The backend tab changed outside this app. No data was overwritten. Reconcile it before retrying.")
                    if hasattr(self.publisher, "commit"):
                        confirmed = self.publisher.commit(desired, remote)
                        if confirmed is None:
                            raise DataError("Google did not confirm the update. Reload before retrying.")
                        self.publisher.validate(confirmed)
                        if digest(confirmed) != wanted:
                            # Our event was accepted, but a newer accepted event followed it.
                            # Import that verified state rather than claiming it was lost.
                            with self.store.connection:
                                self.restore(confirmed, replace=True)
                            wanted = digest(confirmed)
                    else:
                        self.publisher.write(desired)
                        if digest(self.publisher.read()) != wanted:
                            raise DataError("Google did not confirm the backend contents. Retry sync.")
                with self.store.connection:
                    self.set_meta("published_hash", wanted)
                    self.set_meta("last_sync", self.attendance.now().isoformat())
                self.sync_error = ""
            except Exception as exc:
                self.app.logger.warning("Backend sync failed (%s)", type(exc).__name__)
                self.sync_error = (str(exc) if isinstance(exc, DataError)
                                   else ("Google sync is unavailable. The update was not confirmed." if self.strict
                                         else "Google sync is unavailable. Changes are saved locally and pending sync."))
            self.retry_at = time.monotonic() + 60
        return not self.sync_error

    def status(self):
        with self.store.lock:
            pending = bool(self.publisher and digest(self.export()) != self.meta("published_hash"))
            return {"enabled": bool(self.publisher), "pending": pending,
                    "error": self.sync_error, "last_sync": self.meta("last_sync")}
