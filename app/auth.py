"""Accounts: sign-up, log-in, sessions, lockout and the account page."""

from __future__ import annotations

import hashlib
import secrets
import time
from functools import wraps
from typing import Callable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from . import validation
from .db import get_db
from .listings import get_listing
from .security import client_ip, pseudonym, rate_limit, security_event

bp = Blueprint("auth", __name__)

# Argon2id with the library's current recommended parameters.
hasher = PasswordHasher()
# Used to spend the same time verifying when the email doesn't exist.
_DUMMY_HASH = hasher.hash(secrets.token_urlsafe(24))

MAX_FAILURES_BEFORE_LOCK = 5
MAX_LOCK_SECONDS = 60 * 60


# ---------------------------------------------------------------- sessions


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        current_app.config["SESSION_COOKIE_NAME_GLOZ"],
        token,
        max_age=current_app.config["SESSION_HOURS"] * 3600,
        httponly=True,
        secure=current_app.config["SECURE_COOKIES"],
        samesite="Strict",
        path="/",
    )


def _clear_session_cookie(response) -> None:
    response.delete_cookie(
        current_app.config["SESSION_COOKIE_NAME_GLOZ"],
        path="/",
        secure=current_app.config["SECURE_COOKIES"],
        httponly=True,
        samesite="Strict",
    )


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    db = get_db()
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (_hash_token(token), user_id, now, now + current_app.config["SESSION_HOURS"] * 3600),
    )
    db.commit()
    return token


def load_current_user() -> None:
    g.user = None
    token = request.cookies.get(current_app.config["SESSION_COOKIE_NAME_GLOZ"], "")
    if not token or len(token) > 64:
        return
    row = get_db().execute(
        "SELECT u.id, u.email, u.display_name, u.created_at FROM sessions s "
        "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
        (_hash_token(token), int(time.time())),
    ).fetchone()
    if row is not None:
        g.user = row
        g.session_token_hash = _hash_token(token)


def login_required(view: Callable):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("user") is None:
            flash("Log in to continue.", "info")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------- lockout


def _lock_keys(email: str) -> list[str]:
    return [f"user:{pseudonym(email)}", f"ip:{pseudonym(client_ip())}"]


def _locked_for(keys: list[str]) -> int:
    now = int(time.time())
    user_key, ip_key = keys
    rows = get_db().execute(
        "SELECT MAX(locked_until) AS until FROM login_failures WHERE key IN (?, ?)",
        (user_key, ip_key),
    ).fetchone()
    until = rows["until"] or 0
    return max(0, until - now)


def _record_failure(keys: list[str]) -> None:
    now = int(time.time())
    db = get_db()
    for key in keys:
        row = db.execute("SELECT failures FROM login_failures WHERE key = ?", (key,)).fetchone()
        failures = (row["failures"] if row else 0) + 1
        locked_until = 0
        if failures >= MAX_FAILURES_BEFORE_LOCK:
            # 1 min, 2 min, 4 min ... capped at one hour.
            delay = min(60 * 2 ** (failures - MAX_FAILURES_BEFORE_LOCK), MAX_LOCK_SECONDS)
            locked_until = now + delay
        db.execute(
            "INSERT INTO login_failures (key, failures, locked_until, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET failures = excluded.failures, "
            "locked_until = excluded.locked_until, updated_at = excluded.updated_at",
            (key, failures, locked_until, now),
        )
    # Forget failures older than a day.
    db.execute("DELETE FROM login_failures WHERE updated_at < ?", (now - 86400,))
    db.commit()


def _clear_failures(keys: list[str]) -> None:
    db = get_db()
    db.executemany("DELETE FROM login_failures WHERE key = ?", [(k,) for k in keys])
    db.commit()


def _verify(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ---------------------------------------------------------------- routes


@bp.route("/signup", methods=["GET", "POST"])
@rate_limit(limit=5, window_seconds=600)
def signup():
    if g.user is not None:
        return redirect(url_for("auth.account"))
    errors: dict[str, str] = {}
    values = {"email": "", "display_name": ""}
    if request.method == "POST":
        result = validation.registration(request.form)
        values = {k: result.data.get(k, "") for k in values}
        errors = result.errors
        if result.ok:
            db = get_db()
            exists = db.execute(
                "SELECT 1 FROM users WHERE email = ?", (result.data["email"],)
            ).fetchone()
            if exists:
                security_event("signup_duplicate")
                errors["form"] = "We couldn't create this account. If you already have one, log in instead."
            else:
                cur = db.execute(
                    "INSERT INTO users (email, display_name, password_hash) VALUES (?, ?, ?)",
                    (result.data["email"], result.data["display_name"], hasher.hash(result.data["password"])),
                )
                db.commit()
                security_event("signup")
                token = create_session(cur.lastrowid)
                flash("Welcome to Gloz. Your account is ready.", "success")
                response = make_response(redirect(url_for("auth.account")))
                _set_session_cookie(response, token)
                return response
    status = 400 if errors else 200
    return render_template("auth/signup.html", errors=errors, values=values), status


@bp.route("/login", methods=["GET", "POST"])
@rate_limit(limit=10, window_seconds=300)
def login():
    if g.user is not None:
        return redirect(url_for("auth.account"))
    errors: dict[str, str] = {}
    email_value = ""
    if request.method == "POST":
        result = validation.login(request.form)
        if not result.ok:
            errors = result.errors
        else:
            email_value = result.data["email"]
            keys = _lock_keys(email_value)
            wait = _locked_for(keys)
            if wait:
                security_event("login_locked")
                errors["form"] = "Too many attempts. Wait a few minutes and try again."
            else:
                row = get_db().execute(
                    "SELECT id, password_hash FROM users WHERE email = ?", (email_value,)
                ).fetchone()
                ok = _verify(row["password_hash"] if row else _DUMMY_HASH, result.data["password"])
                if row is not None and ok:
                    _clear_failures(keys)
                    if hasher.check_needs_rehash(row["password_hash"]):
                        get_db().execute(
                            "UPDATE users SET password_hash = ? WHERE id = ?",
                            (hasher.hash(result.data["password"]), row["id"]),
                        )
                        get_db().commit()
                    security_event("login_ok")
                    token = create_session(row["id"])
                    response = make_response(redirect(url_for("auth.account")))
                    _set_session_cookie(response, token)
                    return response
                _record_failure(keys)
                security_event("login_failed")
                errors["form"] = "Email or password is incorrect."
    status = 400 if errors else 200
    return render_template("auth/login.html", errors=errors, email=email_value), status


@bp.post("/logout")
def logout():
    if g.user is not None:
        get_db().execute("DELETE FROM sessions WHERE token_hash = ?", (g.session_token_hash,))
        get_db().commit()
        security_event("logout")
    flash("You're logged out.", "info")
    response = make_response(redirect(url_for("main.index")))
    _clear_session_cookie(response)
    return response


@bp.get("/account")
@login_required
def account():
    rows = get_db().execute(
        "SELECT listing_id FROM saved_listings WHERE user_id = ? ORDER BY saved_at DESC",
        (g.user["id"],),
    ).fetchall()
    saved = [listing for r in rows if (listing := get_listing(r["listing_id"])) is not None]
    return render_template("auth/account.html", saved=saved, errors={})


@bp.post("/account/password")
@login_required
@rate_limit(limit=5, window_seconds=600)
def change_password():
    result = validation.password_change(request.form, g.user["email"])
    db = get_db()
    if result.ok:
        row = db.execute("SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)).fetchone()
        if not _verify(row["password_hash"], result.data["current_password"]):
            result.errors["current_password"] = "Your current password is incorrect."
            security_event("password_change_failed")
    if not result.ok:
        rows = db.execute(
            "SELECT listing_id FROM saved_listings WHERE user_id = ?", (g.user["id"],)
        ).fetchall()
        saved = [listing for r in rows if (listing := get_listing(r["listing_id"])) is not None]
        return render_template("auth/account.html", saved=saved, errors=result.errors), 400

    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hasher.hash(result.data["new_password"]), g.user["id"]),
    )
    # Changing the password signs out every other device.
    db.execute("DELETE FROM sessions WHERE user_id = ?", (g.user["id"],))
    db.commit()
    security_event("password_changed")
    token = create_session(g.user["id"])
    flash("Password updated. Other devices were signed out.", "success")
    response = make_response(redirect(url_for("auth.account")))
    _set_session_cookie(response, token)
    return response


@bp.post("/account/delete")
@login_required
@rate_limit(limit=5, window_seconds=600)
def delete_account():
    if request.form.get("confirm", "") != "DELETE":
        flash("Type DELETE to confirm.", "error")
        return redirect(url_for("auth.account"))
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (g.user["id"],))  # cascades to sessions and saves
    db.commit()
    security_event("account_deleted")
    flash("Your account and saved homes were deleted.", "info")
    response = make_response(redirect(url_for("main.index")))
    _clear_session_cookie(response)
    return response


@bp.post("/listings/<listing_id>/save")
@login_required
@rate_limit(limit=60, window_seconds=60)
def toggle_save(listing_id: str):
    listing = get_listing(listing_id)
    if listing is None:
        abort(404)
    db = get_db()
    removed = db.execute(
        "DELETE FROM saved_listings WHERE user_id = ? AND listing_id = ?",
        (g.user["id"], listing.id),
    ).rowcount
    if not removed:
        db.execute(
            "INSERT INTO saved_listings (user_id, listing_id) VALUES (?, ?)",
            (g.user["id"], listing.id),
        )
    db.commit()
    flash("Removed from saved homes." if removed else "Saved to your account.", "success")
    return redirect(url_for("main.listing_detail", listing_id=listing.id))
