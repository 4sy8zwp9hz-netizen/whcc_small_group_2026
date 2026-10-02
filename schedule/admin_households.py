"""Leader roster setup and attendance correction, using the existing backend."""
import hashlib
import json
import re
import secrets

from flask import abort, redirect, request, url_for

from .attendance import clean_name
from .backend import digest, encode
from .data import DataError


def install_households(app, backend, attendance, signed_in, page):
    store = attendance.store

    def households():
        return [{"id": r["id"], "name": r["name"], "members": json.loads(r["members"])}
                for r in store.connection.execute("SELECT * FROM households ORDER BY name COLLATE NOCASE,id")]

    def public_id(identity):
        return identity[7:] if identity.startswith("import:") else hashlib.sha256(identity.encode()).hexdigest()

    def state(identity, meeting_id):
        profile = next((h for h in households() if public_id(h["id"]) == identity), None)
        record = next((r for r in backend.records() if r["id"] == meeting_id), None)
        reply = None
        if profile and record:
            row = store.connection.execute("SELECT attending,updated_at FROM responses WHERE household_id=? AND meeting_id=?",
                                           (profile["id"], meeting_id)).fetchone()
            reply = {**dict(row), "attending": json.loads(row["attending"])} if row else None
        return profile, record, reply

    def token_for(profile, record, reply):
        canonical = {**profile, "id": public_id(profile["id"])} if profile else None
        return digest([canonical, record, reply])

    @app.route("/admin/households", methods=["GET", "POST"])
    def admin_households():
        if not signed_in():
            return redirect(url_for("admin_login"))
        if request.method == "POST" and not attendance.csrf_valid():
            abort(400)
        snapshot = backend.cache.get()
        selected = request.values.get("household_id", "")
        meeting_id = request.values.get("meeting_id", "")
        error, code = "", 200
        base = None
        if request.method == "POST":
            try:
                with store.lock, store.connection:
                    base = backend.refresh_remote() if backend.strict else None
                    if not attendance.schedule_usable(snapshot) or not backend.records():
                        raise DataError("The saved backend could not be verified. Reload before saving.")
                    profile, record, reply = state(selected, meeting_id)
                    if request.form.get("token") != token_for(profile, record, reply):
                        raise DataError("This household or meeting changed. Reload and review before saving.")
                    if selected and profile is None:
                        raise DataError("That household no longer exists. Reload before saving.")
                    name = clean_name(request.form.get("name", ""))
                    members = []
                    if profile:
                        members = [{"id": m["id"], "name": clean_name(request.form.get("member_" + m["id"], ""), 40)}
                                   for m in profile["members"]]
                    new_names = [clean_name(n, 40) for n in re.split(r"[,\n]", request.form.get("new_people", "")) if n.strip()]
                    members += [{"id": secrets.token_hex(12), "name": n} for n in new_names]
                    surname = request.form.get("family_last_name", "").strip()
                    if surname:
                        surname = clean_name(surname, 40)
                        members = [{**m, "name": clean_name(m["name"] + " " + surname, 40)
                                    if len(m["name"].split()) == 1 else m["name"]} for m in members]
                    if not 1 <= len(members) <= 20 or len({m["name"].casefold() for m in members}) != len(members):
                        raise ValueError("Use 1–20 people with distinct names or nicknames.")
                    identity = profile["id"] if profile else "import:" + secrets.token_hex(32)
                    store.connection.execute("INSERT INTO households VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,members=excluded.members",
                                             (identity, name, encode(members)))
                    action = request.form.get("action", "")
                    if action != "profile":
                        current = next((m for m in backend.cache.parser(backend.rows()) if attendance.key(m) == meeting_id), None)
                        if current is None or not attendance.allowed(current, snapshot):
                            raise DataError("Choose an upcoming, confirmed meeting before changing attendance.")
                        store.save(identity, meeting_id, action, name, "", request.form.getlist("attending"), attendance.now().isoformat())
                    if backend.strict and not backend.publish(force=True, base=base):
                        raise DataError("The change was not confirmed in Sheets. Reload before retrying.")
                if not backend.strict:
                    backend.publish(force=True)
                return redirect(url_for("admin_households", household_id=public_id(identity), meeting_id=meeting_id, saved="yes"), code=303)
            except (ValueError, DataError) as exc:
                if base is not None:
                    with store.lock, store.connection:
                        backend.restore(base, replace=True)
                error, code = str(exc), 409 if isinstance(exc, DataError) else 400
            except Exception:
                if base is not None:
                    with store.lock, store.connection:
                        backend.restore(base, replace=True)
                app.logger.warning("Admin household save unavailable")
                error, code = "The change could not be confirmed. Reload before retrying.", 503
        with store.lock:
            profile, record, reply = state(selected, meeting_id)
            roster = [{**h, "id": public_id(h["id"])} for h in households()]
            meetings = backend.cache.parser(backend.rows())
            choices = [m for m in meetings if attendance.allowed(m, snapshot)]
            selected_ids = reply["attending"] if reply else [m["id"] for m in profile["members"]] if profile else []
            token = token_for(profile, record, reply)
        return page("admin_households.html", roster=roster, profile=profile, selected=selected,
                    meeting_id=meeting_id, choices=choices, selected_ids=selected_ids, token=token,
                    error=error, saved=request.args.get("saved") == "yes", sync=backend.status(),
                    available=attendance.schedule_usable(snapshot) and bool(backend.records())), code
