"""Password-protected admin editing with CSRF and optimistic revisions."""
import hashlib
import secrets
import time

import click
from flask import abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .backend import EDIT_FIELDS, digest
from .data import DataError


def install_admin(app, root, backend, attendance):
    password_path = root / app.config["ADMIN_PASSWORD_FILE"]
    from .login_limiter import LoginLimiter
    limiter = LoginLimiter()

    def password_hash():
        configured = app.config.get("ADMIN_PASSWORD_HASH")
        if configured:
            return configured
        return password_path.read_text(encoding="utf-8").strip() if password_path.exists() else ""

    def csrf():
        attendance.visitor()
        return session["csrf"]

    def signed_in():
        configured = password_hash()
        return bool(configured and session.get("admin_until", 0) > time.time()
                    and session.get("admin_credential") == hashlib.sha256(configured.encode()).hexdigest())

    def page(template, **context):
        return render_template(template, csrf=csrf(), logged_in=signed_in(), **context)

    from .admin_households import install_households
    install_households(app, backend, attendance, signed_in, page)

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        configured = password_hash()
        error = ""
        code = 200
        if request.method == "POST":
            if not attendance.csrf_valid():
                abort(400)
            identity = attendance.visitor()
            if limiter.blocked(identity):
                error, code = "Too many attempts. Try again in five minutes.", 429
            else:
                supplied = request.form.get("password", "")
                configured = configured
                if configured and len(supplied) <= 512 and check_password_hash(configured, supplied):
                    limiter.success(identity)
                    session["admin_until"] = time.time() + 1800
                    session["admin_credential"] = hashlib.sha256(configured.encode()).hexdigest()
                    session["csrf"] = secrets.token_urlsafe(32)
                    return redirect(url_for("admin_index"), code=303)
                limiter.failure(identity)
                error, code = "The admin password was not accepted.", 401
        return page("admin_login.html", configured=bool(configured), error=error), code

    @app.post("/admin/logout")
    def admin_logout():
        if not attendance.csrf_valid():
            abort(400)
        session.pop("admin_until", None)
        session.pop("admin_credential", None)
        session["csrf"] = secrets.token_urlsafe(32)
        return redirect(url_for("upcoming"), code=303)

    @app.get("/admin")
    def admin_index():
        if not signed_in():
            return redirect(url_for("admin_login"))
        snapshot = backend.cache.get()
        return page("admin_index.html", records=backend.records(), sync=backend.status(), stale=snapshot.stale)

    @app.route("/admin/meetings/<key>", methods=["GET", "POST"])
    def admin_edit(key):
        if not signed_in():
            return redirect(url_for("admin_login"))
        if request.method == "POST" and not attendance.csrf_valid():
            abort(400)
        if request.method == "POST":
            backend.invalidate()
        snapshot = backend.cache.get()
        record = next((r for r in backend.records() if r["id"] == key), None)
        if record is None:
            abort(404)
        error, code = "", 200
        editing_available = not snapshot.stale or (backend.strict and backend.attendance_available)
        values = record["values"].copy()
        if request.method == "POST":
            values = {f: request.form.get(f, "").strip() for f in EDIT_FIELDS if f != "special_event"}
            values["special_event"] = request.form.get("special_event") == "true"
            try:
                if not editing_available:
                    raise DataError("The saved backend could not be verified. Reload before editing.")
                backend.edit(key, request.form.get("revision", ""), values,
                             {field: request.form.get("resolve_" + field) for field in record["conflicts"]})
                return redirect(url_for("admin_index"), code=303)
            except DataError as exc:
                error, code = str(exc), 409
            except ValueError:
                error, code = "Check the date and time, then try again.", 400
        return page("admin_edit.html", record=record, values=values, fields=EDIT_FIELDS,
                    error=error, stale=snapshot.stale, editing_available=editing_available,
                    version_conflict=(request.method == "POST" and
                                      request.form.get("revision") != str(record["revision"]))), code

    @app.post("/admin/sync")
    def admin_sync():
        if not signed_in():
            return redirect(url_for("admin_login"))
        if not attendance.csrf_valid():
            abort(400)
        backend.invalidate()
        snapshot = backend.cache.get()
        if not snapshot.stale:
            backend.publish(force=True)
        return redirect(url_for("admin_index"), code=303)

    @app.route("/admin/recovery", methods=["GET", "POST"])
    def admin_recovery():
        if not signed_in():
            return redirect(url_for("admin_login"))
        if request.method == "POST" and not attendance.csrf_valid():
            abort(400)
        if not backend.publisher or not hasattr(backend.publisher, "decode_table"):
            return page("admin_recovery.html", plan=None, error="Google backend recovery is unavailable in local demo mode.", recovered=None), 409
        from .recovery import BackendRecovery
        recovery = BackendRecovery(backend.publisher)
        error, code, recovered, plan = "", 200, None, None
        try:
            with backend.store.lock:
                if request.method == "POST":
                    if request.form.get("writers_stopped") != "yes":
                        raise DataError("Confirm that other writers are stopped before recovery.")
                    recovered = recovery.repair(request.form.get("token", ""))
                    backend.sync_error = ""
                plan = recovery.preview()
            if recovered:
                backend.invalidate()
                backend.cache.get()
        except Exception as exc:
            error = str(exc) if isinstance(exc, DataError) else "Recovery could not be confirmed. Check the retained backup before retrying."
            code = 409 if isinstance(exc, DataError) else 503
        return page("admin_recovery.html", plan=plan, error=error, recovered=recovered), code

    @app.route("/admin/recovery/rebuild", methods=["GET", "POST"])
    def admin_rebuild():
        if not signed_in():
            return redirect(url_for("admin_login"))
        if request.method == "POST" and not attendance.csrf_valid():
            abort(400)
        from .recovery import BackendRecovery
        plan, error, recovered, code = None, "", None, 200
        try:
            if not backend.publisher or not hasattr(backend.publisher, "decode_table"):
                raise DataError("Google backend rebuild is unavailable in local demo mode.")
            recovery = BackendRecovery(backend.publisher)
            with backend.store.lock:
                if request.method == "POST":
                    if request.form.get("writers_stopped") != "yes" or request.form.get("confirm_rebuild") != "REBUILD":
                        raise DataError("Confirm stopped writers and type REBUILD before continuing.")
                    recovered = recovery.rebuild(request.form.get("token", ""))
                    backend.sync_error = ""
                plan = recovery.rebuild_preview()
            if recovered:
                backend.invalidate()
                backend.cache.get()
        except Exception as exc:
            error = str(exc) if isinstance(exc, DataError) else "Rebuild could not be confirmed. Check the retained backup before retrying."
            code = 409 if isinstance(exc, DataError) else 503
        return page("admin_rebuild.html", plan=plan, error=error, recovered=recovered), code

    @app.cli.command("set-admin-password")
    @click.password_option(confirmation_prompt=True)
    def set_admin_password(password):
        """Set a shared admin password locally without storing plaintext."""
        if app.config.get("ADMIN_PASSWORD_HASH"):
            raise click.ClickException("ADMIN_PASSWORD_HASH is configured. Change that server secret instead.")
        if len(password) < 12 or len(password) > 512:
            raise click.ClickException("Use a password between 12 and 512 characters.")
        password_path.parent.mkdir(parents=True, exist_ok=True)
        password_path.write_text(generate_password_hash(password), encoding="utf-8")
        click.echo("Admin password updated. Existing admin sessions are invalidated.")

    @app.cli.command("init-sheet-backend")
    def init_sheet_backend():
        """Create the configured new tab from the current normalized schedule."""
        if not backend.publisher:
            raise click.ClickException("Set BACKEND_SHEET_ENABLED=true with DATA_SOURCE=google.")
        snapshot = backend.cache.get()
        if snapshot.stale or snapshot.meetings is None:
            raise click.ClickException("The source calendar could not be read; no tab was created.")
        with backend.store.lock:
            payload = backend.export()
            try:
                sheet_id = backend.publisher.create(payload)
                verified = backend.publisher.read()
                if digest(verified) != digest(payload):
                    raise DataError("The created tab could not be verified. Retry sync before using it.")
                with backend.store.connection:
                    backend.set_meta("published_hash", digest(payload))
                    backend.set_meta("last_sync", attendance.now().isoformat())
                backend.sync_error = ""
            except Exception as exc:
                raise click.ClickException(
                    str(exc) if isinstance(exc, DataError) else
                    "Google could not create the backend tab. Check service-account Editor access and retry."
                ) from None
        click.echo("Backend tab created and verified. Sheet gid: " + str(sheet_id))
