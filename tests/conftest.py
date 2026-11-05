import re
import secrets

import pytest

from app import create_app
from app.security import limiter

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
STRONG_PASSWORD = "harbour-maple-lantern-42"


@pytest.fixture()
def app(tmp_path):
    limiter.reset()
    app = create_app(
        {
            "GLOZ_ENV": "test",
            "SECRET_KEY": secrets.token_urlsafe(48),
            "IP_HASH_SALT": secrets.token_urlsafe(24),
            "DATABASE_PATH": str(tmp_path / "test.sqlite3"),
            "LOG_DIR": str(tmp_path / "logs"),
        }
    )
    yield app
    limiter.reset()


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf(client, path="/login"):
    response = client.get(path)
    match = CSRF_RE.search(response.get_data(as_text=True))
    assert match, f"no CSRF token on {path}"
    return match.group(1)


def signup(client, email="ana@example.com", name="Ana", password=STRONG_PASSWORD):
    token = csrf(client, "/signup")
    return client.post(
        "/signup",
        data={
            "csrf_token": token,
            "email": email,
            "display_name": name,
            "password": password,
            "password_confirm": password,
        },
    )


def login(client, email="ana@example.com", password=STRONG_PASSWORD):
    token = csrf(client, "/login")
    return client.post("/login", data={"csrf_token": token, "email": email, "password": password})
