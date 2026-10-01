"""Household attendance stored separately from the read-only schedule."""
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import threading

from flask import jsonify, redirect, render_template, request, session, url_for


def clean_name(value, limit=60):
    value = " ".join(value.split())
    if not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f"Use a name between 1 and {limit} characters.")
    return value


def load_secret(path):
    """Generate once for local use so remembered households survive restarts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    secret = path.read_text(encoding="utf-8").strip()
    if len(secret) < 32:
        raise ValueError("The attendance session secret must be at least 32 characters.")
    return secret


class AttendanceStore:
    def __init__(self, path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(str(path), timeout=5, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        with self.connection:
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS households (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    members TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS responses (
                    meeting_id TEXT NOT NULL,
                    household_id TEXT NOT NULL REFERENCES households(id),
                    attending TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (meeting_id, household_id)
                );
            """)

    def household(self, visitor):
        with self.lock:
            row = self.connection.execute(
                "SELECT name, members FROM households WHERE id = ?", (visitor,)
            ).fetchone()
        return {"name": row["name"], "members": json.loads(row["members"])} if row else None

    def save(self, visitor, meeting_id, action, name, people, selected, updated_at):
        with self.lock, self.connection:
            household = self.household(visitor)
            if household is None:
                if action not in {"all", "none"}:
                    raise ValueError("Enter your household first, then choose All going or Not going.")
                household_name = clean_name(name)
                names = [clean_name(part, 40) for part in re.split(r"[,\n]", people) if part.strip()]
                if not 1 <= len(names) <= 20:
                    raise ValueError("Enter between 1 and 20 people, separated by commas.")
                if len({name.casefold() for name in names}) != len(names):
                    raise ValueError("Give each person a distinct name or nickname.")
                members = [{"id": secrets.token_hex(12), "name": name} for name in names]
                household = {"name": household_name, "members": members}
                self.connection.execute(
                    "INSERT INTO households (id, name, members) VALUES (?, ?, ?)",
                    (visitor, household_name, json.dumps(members)),
                )
            member_ids = [member["id"] for member in household["members"]]
            if action == "clear":
                self.connection.execute(
                    "DELETE FROM responses WHERE meeting_id = ? AND household_id = ?",
                    (meeting_id, visitor),
                )
                return
            if action == "all":
                attending = member_ids
            elif action == "none":
                attending = []
            elif action == "custom":
                if not set(selected).issubset(member_ids):
                    raise ValueError("That person is not in the remembered household.")
                attending = [member_id for member_id in member_ids if member_id in selected]
            else:
                raise ValueError("Choose a valid attendance response.")
            self.connection.execute("""
                INSERT INTO responses (meeting_id, household_id, attending, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(meeting_id, household_id) DO UPDATE SET
                    attending = excluded.attending, updated_at = excluded.updated_at
                """, (meeting_id, visitor, json.dumps(attending), updated_at))

    def summaries(self, meeting_ids, visitor):
        result = {key: {"own": None, "going": [], "not_going": 0, "people": 0}
                  for key in meeting_ids}
        if not result:
            return result
        placeholders = ",".join("?" for _ in result)
        with self.lock:
            rows = self.connection.execute(f"""
                SELECT r.meeting_id, r.household_id, r.attending, h.name, h.members
                FROM responses r JOIN households h ON h.id = r.household_id
                WHERE r.meeting_id IN ({placeholders})
                ORDER BY h.name COLLATE NOCASE
                """, tuple(result)).fetchall()
        for row in rows:
            summary = result[row["meeting_id"]]
            attending = json.loads(row["attending"])
            if row["household_id"] == visitor:
                summary["own"] = attending
            names = [member["name"] for member in json.loads(row["members"])
                     if member["id"] in attending]
            if names:
                summary["going"].append({"household": row["name"], "names": names})
                summary["people"] += len(names)
            else:
                summary["not_going"] += 1
        return result


class Attendance:
    def __init__(self, app, root, cache, now):
        self.app, self.cache, self.now = app, cache, now
        if not app.config.get("SECRET_KEY"):
            app.secret_key = (secrets.token_hex(32) if app.testing else
                              load_secret(root / app.config["RSVP_SECRET_FILE"]))
        database = app.config["RSVP_DATABASE"]
        self.store = AttendanceStore(database if database == ":memory:" else root / database)
        if app.config["DATA_SOURCE"] == "google":
            source = app.config["GOOGLE_SHEET_ID"] + "\0" + app.config["GOOGLE_SHEET_RANGE"].split("!")[0]
        else:
            source = str((root / app.config["CSV_PATH"]).resolve())
        self.namespace = app.config["DATA_SOURCE"] + "\0" + source
        app.add_url_rule("/attendance/<meeting_id>", "save_attendance", self.save, methods=["POST"])
        app.add_url_rule("/household/forget", "forget_household", self.forget, methods=["POST"])

    def key(self, meeting):
        # Date is stable across topic/assignment/time edits. Ambiguous dates cannot RSVP.
        value = self.namespace + "\0" + meeting.starts_at.date().isoformat()
        return hashlib.sha256(value.encode()).hexdigest()[:32]

    def visitor(self):
        if "household_id" not in session:
            session["household_id"] = secrets.token_urlsafe(32)
            session["csrf"] = secrets.token_urlsafe(32)
            session.permanent = True
        return session["household_id"]

    def allowed(self, meeting, snapshot):
        return (not snapshot.stale and not meeting.canceled and not meeting.date_conflict
                and meeting.starts_at >= self.now())

    def context(self, meetings, snapshot):
        visitor = self.visitor()
        household = self.store.household(visitor)
        keys = [self.key(meeting) for meeting in meetings]
        return {
            "household": household, "csrf": session["csrf"],
            "attendance": self.store.summaries(keys, visitor),
            "attendance_key": self.key,
            "can_respond": lambda meeting: self.allowed(meeting, snapshot),
        }

    def csrf_valid(self):
        token = request.form.get("csrf", "")
        expected = session.get("csrf", "")
        return bool(expected and secrets.compare_digest(token.encode(), expected.encode()))

    def error(self, message, code):
        if request.accept_mimetypes.best == "application/json":
            return jsonify(error=message), code
        return render_template("attendance_error.html", message=message), code

    def save(self, meeting_id):
        if not self.csrf_valid():
            return self.error("Please reload the page and try again.", 400)
        snapshot = self.cache.get()
        if snapshot.meetings is None or snapshot.stale:
            return self.error("The schedule could not refresh. Your response was not changed. Try again shortly.", 503)
        matches = [meeting for meeting in snapshot.meetings if self.key(meeting) == meeting_id]
        if len(matches) != 1 or not self.allowed(matches[0], snapshot):
            return self.error("Attendance is closed or this meeting needs confirmation. Reload the schedule.", 409)
        action = request.form.get("action", "")
        if action not in {"all", "none", "custom", "clear"}:
            return self.error("Choose a valid attendance response.", 400)
        try:
            self.store.save(
                self.visitor(), meeting_id, action, request.form.get("household", ""),
                request.form.get("people", ""), request.form.getlist("attending"),
                self.now().isoformat(),
            )
        except ValueError as exc:
            return self.error(str(exc), 400)
        except sqlite3.Error:
            self.app.logger.warning("Attendance storage unavailable")
            return self.error("Attendance could not be saved. Please try again.", 503)
        if request.accept_mimetypes.best != "application/json":
            return redirect(url_for("upcoming", _anchor="meeting-" + meeting_id), code=303)
        context = self.context(snapshot.meetings, snapshot)
        panels = {
            self.key(meeting): render_template("_attendance.html", meeting=meeting, **context)
            for meeting in snapshot.meetings
            if meeting.starts_at >= self.now() and not meeting.canceled
        }
        return jsonify(panels=panels, message="Response cleared." if action == "clear" else "Attendance saved.")

    def forget(self):
        if not self.csrf_valid():
            return self.error("Please reload the page and try again.", 400)
        # Existing replies remain intact. Only this browser's remembered identity changes.
        session.clear()
        return redirect(url_for("upcoming"), code=303)
