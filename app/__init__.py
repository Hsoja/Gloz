"""Gloz: a home and property listings web app built with Flask."""

from __future__ import annotations

from datetime import timedelta

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException

from .config import Settings, load_settings

ERROR_COPY = {
    400: ("This request couldn't be processed", "Reload the page and try again."),
    404: ("This page doesn't exist", "The link may be old, or the listing is no longer available."),
    405: ("That action isn't allowed here", "Go back and use the buttons on the page."),
    413: ("That form was too large", "Shorten what you entered and send it again."),
    429: ("Too many requests", "Wait a minute before trying again."),
    500: ("Something went wrong on our side", "Try again in a moment."),
}


def create_app(overrides: dict[str, str] | None = None) -> Flask:
    settings: Settings = load_settings(overrides)

    app = Flask(__name__, instance_relative_config=False)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        IP_HASH_SALT=settings.ip_hash_salt,
        DATABASE_PATH=settings.database_path,
        LOG_DIR=settings.log_dir,
        SESSION_HOURS=settings.session_hours,
        TRUSTED_PROXIES=settings.trusted_proxies,
        IS_PRODUCTION=settings.is_production,
        SECURE_COOKIES=settings.secure_cookies,
        SESSION_COOKIE_NAME_GLOZ=settings.session_cookie_name,
        CSRF_COOKIE_NAME=settings.csrf_cookie_name,
        TESTING=settings.env == "test",
        DEBUG=False,
        # Flask's own signed cookie only carries one-time flash messages.
        SESSION_COOKIE_NAME="gloz_flash",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=settings.secure_cookies,
        SESSION_COOKIE_SAMESITE="Strict",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
        SEND_FILE_MAX_AGE_DEFAULT=timedelta(days=7),
        TEMPLATES_AUTO_RELOAD=settings.env == "development",
    )

    from . import auth, db, security, views

    db.init_db(app)
    security.init_security(app)
    app.before_request(auth.load_current_user)

    app.register_blueprint(views.bp)
    app.register_blueprint(auth.bp)

    @app.errorhandler(HTTPException)
    def _http_error(exc: HTTPException):
        code = exc.code or 500
        title, hint = ERROR_COPY.get(code, (exc.name, "Go back and try again."))
        return render_template("error.html", code=code, title=title, hint=hint), code

    @app.errorhandler(Exception)
    def _unexpected(exc: Exception):
        # Full detail goes to the server log with the request id; the client sees a generic page.
        app.logger.exception("unhandled error on %s", request.path)
        title, hint = ERROR_COPY[500]
        return render_template("error.html", code=500, title=title, hint=hint), 500

    @app.context_processor
    def _globals():
        return {"is_production": settings.is_production}

    return app
