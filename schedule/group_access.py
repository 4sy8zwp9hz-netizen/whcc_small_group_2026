"""Shared group gate, independent of admin authorization."""
import hashlib
import secrets
import threading
import time
from collections import deque
from flask import abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash


def install_group_access(app, attendance):
    attempts = deque()
    lock = threading.Lock()
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
            with lock:
                while attempts and attempts[0] < time.monotonic() - 300:
                    attempts.popleft()
                if len(attempts) >= 10:
                    error, code = "Too many attempts. Try again in five minutes.", 429
                else:
                    attempts.append(time.monotonic())
                    supplied = request.form.get("password", "")
                    configured = app.config["GROUP_ACCESS_PASSWORD_HASH"]
                    if configured and len(supplied) <= 512 and check_password_hash(configured, supplied):
                        session["group_until"] = time.time() + 86400
                        session["group_credential"] = fingerprint()
                        session["csrf"] = secrets.token_urlsafe(32)
                        return redirect(url_for("upcoming"), code=303)
                    error, code = "The group password was not accepted.", 401
        return render_template("group_login.html", csrf=session["csrf"], error=error), code
    @app.post("/group/logout")
    def group_logout():
        if not attendance.csrf_valid():
            abort(400)
        for key in ("group_until", "group_credential", "admin_until", "admin_credential"):
            session.pop(key, None)
        return redirect(url_for("group_login"), code=303)
