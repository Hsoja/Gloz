"""Cross-cutting security controls: headers, CSRF, rate limiting and the security log."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import threading
import time
import uuid
from collections import defaultdict, deque
from functools import wraps
from logging.handlers import RotatingFileHandler
from typing import Callable
from urllib.parse import urlsplit

from flask import Flask, abort, current_app, g, request

CSRF_FIELD = "csrf_token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
MAX_BODY_BYTES = 16 * 1024  # forms on this site are tiny

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "object-src 'none'",
    ]
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


# ---------------------------------------------------------------- client IP


def client_ip() -> str:
    """Return the caller's IP. X-Forwarded-For is only trusted from TRUSTED_PROXIES."""
    remote = request.remote_addr or "unknown"
    trusted = current_app.config["TRUSTED_PROXIES"]
    if remote in trusted:
        forwarded = request.headers.get("X-Forwarded-For", "")
        candidate = forwarded.split(",")[-1].strip() if forwarded else ""
        try:
            ipaddress.ip_address(candidate)
            return candidate
        except ValueError:
            pass
    return remote


def pseudonym(value: str) -> str:
    """Salted hash so logs can correlate events without storing personal data."""
    salt = current_app.config["IP_HASH_SALT"].encode()
    return hmac.new(salt, value.encode(), hashlib.sha256).hexdigest()[:16]


# ---------------------------------------------------------------- security log

_security_logger = logging.getLogger("gloz.security")


def _setup_security_log(app: Flask) -> None:
    for old in list(_security_logger.handlers):
        _security_logger.removeHandler(old)
        old.close()
    log_dir = app.config["LOG_DIR"]
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "security.jsonl", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _security_logger.addHandler(handler)
    _security_logger.setLevel(logging.INFO)
    _security_logger.propagate = False


def security_event(event: str, **fields: str | int) -> None:
    """Write one JSON line. Never pass emails, passwords, tokens or raw IPs here."""
    record = {
        "ts": int(time.time()),
        "event": event,
        "request_id": getattr(g, "request_id", "-"),
        "ip": pseudonym(client_ip()),
        "path": request.path,
        **fields,
    }
    _security_logger.info(json.dumps(record, separators=(",", ":")))


# ---------------------------------------------------------------- rate limiting


class RateLimiter:
    """Small in-memory sliding-window limiter (one process). Use Redis when scaling out."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def rate_limit(limit: int, window_seconds: int, methods: frozenset[str] = frozenset({"POST"})):
    """Limit requests per client IP and route."""

    def decorator(view: Callable):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if request.method in methods:
                key = f"{request.endpoint}:{client_ip()}"
                if not limiter.hit(key, limit, window_seconds):
                    security_event("rate_limited", endpoint=request.endpoint or "-")
                    abort(429)
            return view(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------- CSRF (double-submit token)


def csrf_token() -> str:
    token = getattr(g, "csrf_token", None)
    if token is None:
        cookie = request.cookies.get(current_app.config["CSRF_COOKIE_NAME"], "")
        token = cookie if len(cookie) == 43 else secrets.token_urlsafe(32)
        g.csrf_token = token
        g.csrf_new = token != cookie
    return token


def _same_origin() -> bool:
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        return True  # some privacy tools strip both; the token check still applies
    return urlsplit(origin).netloc == request.host


def _check_csrf() -> None:
    if request.method not in UNSAFE_METHODS:
        return
    cookie = request.cookies.get(current_app.config["CSRF_COOKIE_NAME"], "")
    sent = request.form.get(CSRF_FIELD, "")
    if not cookie or not sent or not hmac.compare_digest(cookie, sent) or not _same_origin():
        security_event("csrf_rejected")
        abort(400)


# ---------------------------------------------------------------- wiring


def init_security(app: Flask) -> None:
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    _setup_security_log(app)

    @app.before_request
    def _before() -> None:
        g.request_id = uuid.uuid4().hex[:12]
        _check_csrf()

    @app.after_request
    def _after(response):
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if app.config["IS_PRODUCTION"]:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        if getattr(g, "csrf_new", False):
            response.set_cookie(
                app.config["CSRF_COOKIE_NAME"],
                g.csrf_token,
                httponly=True,
                secure=app.config["SECURE_COOKIES"],
                samesite="Strict",
                path="/",
            )
        return response

    app.jinja_env.globals["csrf_token"] = csrf_token
