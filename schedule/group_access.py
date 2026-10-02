"""Shared group gate, independent of admin authorization."""
import hashlib
import secrets
import time
from flask import abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash


GROUP_ACCESS_SECONDS = 24 * 60 * 60
REMEMBERED_GROUP_ACCESS_SECONDS = 30 * GROUP_ACCESS_SECONDS


def install_group_access(app, attendance):
    from .login_limiter import LoginLimiter
    limiter = LoginLimiter()
    def fingerprint():
        return hashlib.sha256(app.config["GROUP_ACCESS_PASSWORD_HASH"].encode()).hexdigest()
    def authorized():
        return (session.get("group_until", 0) > time.time()
                and session.get("group_credential") == fingerprint())
    @app.before_request
    def gate():
        if (app.config["GROUP_ACCESS_PASSWORD_HASH"] and request.endpoint not in
                {"health", "static", "group_login"} and not authorized()):
            if request.method != "GET":
                abort(401)
            return redirect(url_for("group_login"), code=303)
    @app.route("/group/login", methods=["GET", "POST"])
    def group_login():
        attendance.visitor()
        error, code = "", 200
        if request.method == "POST":
            if not attendance.csrf_valid():
                abort(400)
            identity = attendance.visitor()
            if limiter.blocked(identity):
                error, code = "Too many attempts. Try again in five minutes.", 429
            else:
                supplied = request.form.get("password", "")
                configured = app.config["GROUP_ACCESS_PASSWORD_HASH"]
                if configured and len(supplied) <= 512 and check_password_hash(configured, supplied):
                    limiter.success(identity)
                    remembered = request.form.getlist("remember_device") == ["30_days"]
                    duration = REMEMBERED_GROUP_ACCESS_SECONDS if remembered else GROUP_ACCESS_SECONDS
                    session["group_until"] = time.time() + duration
                    session["group_credential"] = hashlib.sha256(configured.encode()).hexdigest()
                    session["csrf"] = secrets.token_urlsafe(32)
                    return redirect(url_for("upcoming"), code=303)
                limiter.failure(identity)
                error, code = "The group password was not accepted.", 401
        return render_template("group_login.html", csrf=session["csrf"], error=error), code
    @app.post("/group/logout")
    def group_logout():
        if not attendance.csrf_valid():
            abort(400)
        for key in ("group_until", "group_credential", "admin_until", "admin_credential"):
            session.pop(key, None)
        session["csrf"] = secrets.token_urlsafe(32)
        return redirect(url_for("group_login"), code=303)
