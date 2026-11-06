import sqlite3

from app.security import limiter

from .conftest import STRONG_PASSWORD, csrf, login, signup


def _db(app):
    conn = sqlite3.connect(app.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------- sign-up


def test_signup_creates_account_and_session(client, app):
    response = signup(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/account")
    page = client.get("/account")
    assert page.status_code == 200
    assert "Hi, Ana" in page.get_data(as_text=True)


def test_password_is_stored_as_argon2id(client, app):
    signup(client)
    row = _db(app).execute("SELECT password_hash FROM users").fetchone()
    assert row["password_hash"].startswith("$argon2id$")
    assert STRONG_PASSWORD not in row["password_hash"]


def test_session_token_is_stored_hashed(client, app):
    signup(client)
    cookie = client.get_cookie("gloz_session")
    stored = _db(app).execute("SELECT token_hash FROM sessions").fetchone()["token_hash"]
    assert cookie is not None and cookie.value != stored
    assert len(stored) == 64


def test_session_cookie_flags(client):
    response = signup(client)
    header = next(h for h in response.headers.getlist("Set-Cookie") if h.startswith("gloz_session="))
    assert "HttpOnly" in header
    assert "SameSite=Strict" in header


def test_signup_rejects_weak_password(client):
    response = signup(client, password="short")
    assert response.status_code == 400
    assert "at least 12 characters" in response.get_data(as_text=True)


def test_signup_rejects_mismatched_confirmation(client):
    token = csrf(client, "/signup")
    response = client.post(
        "/signup",
        data={"csrf_token": token, "email": "b@example.com", "display_name": "B", "password": STRONG_PASSWORD, "password_confirm": STRONG_PASSWORD + "x"},
    )
    assert response.status_code == 400


def test_signup_rejects_duplicate_without_confirming_it(client):
    signup(client)
    client.post("/logout", data={"csrf_token": csrf(client, "/")})
    response = signup(client)
    assert response.status_code == 400
    assert "couldn&#39;t create this account" in response.get_data(as_text=True)


def test_signup_rejects_unexpected_fields(client):
    token = csrf(client, "/signup")
    response = client.post(
        "/signup",
        data={"csrf_token": token, "email": "c@example.com", "display_name": "C", "password": STRONG_PASSWORD, "password_confirm": STRONG_PASSWORD, "is_admin": "1"},
    )
    assert response.status_code == 400


def test_display_name_xss_is_escaped(client):
    signup(client, name='<img src=x onerror=alert(1)>')
    html = client.get("/account").get_data(as_text=True)
    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html


def test_sql_injection_in_email_is_rejected(client, app):
    response = signup(client, email="x'@example.com' OR '1'='1")
    assert response.status_code == 400
    assert _db(app).execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


# ---------------------------------------------------------------- CSRF and size


def test_post_without_csrf_is_rejected(client):
    response = client.post("/login", data={"email": "a@example.com", "password": "x"})
    assert response.status_code == 400


def test_post_with_wrong_csrf_is_rejected(client):
    csrf(client, "/login")
    response = client.post("/login", data={"csrf_token": "A" * 43, "email": "a@example.com", "password": "x"})
    assert response.status_code == 400


def test_cross_origin_post_is_rejected(client):
    token = csrf(client, "/login")
    response = client.post(
        "/login",
        data={"csrf_token": token, "email": "a@example.com", "password": "x"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 400


def test_huge_body_is_rejected(client):
    token = csrf(client, "/login")
    response = client.post("/login", data={"csrf_token": token, "email": "a" * 20000, "password": "x"})
    assert response.status_code == 413


# ---------------------------------------------------------------- log-in


def test_login_and_logout(client):
    signup(client)
    client.post("/logout", data={"csrf_token": csrf(client, "/")})
    assert client.get("/account").status_code == 302
    response = login(client)
    assert response.status_code == 302
    assert client.get("/account").status_code == 200


def test_logout_invalidates_server_session(client, app):
    signup(client)
    token = client.get_cookie("gloz_session").value
    client.post("/logout", data={"csrf_token": csrf(client, "/")})
    client.set_cookie("gloz_session", token)
    assert client.get("/account").status_code == 302


def test_wrong_password_and_unknown_email_look_the_same(client):
    signup(client)
    client.post("/logout", data={"csrf_token": csrf(client, "/")})
    wrong = login(client, password="not-the-right-password")
    unknown = login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 400
    assert "Email or password is incorrect." in wrong.get_data(as_text=True)
    assert "Email or password is incorrect." in unknown.get_data(as_text=True)


def test_account_locks_after_repeated_failures(client):
    signup(client)
    client.post("/logout", data={"csrf_token": csrf(client, "/")})
    for _ in range(5):
        login(client, password="wrong-password-123")
    locked = login(client)  # even the right password is refused while locked
    assert locked.status_code == 400
    assert "Too many attempts" in locked.get_data(as_text=True)


def test_login_is_rate_limited(client):
    limiter.reset()
    statuses = [login(client, email=f"u{i}@example.com").status_code for i in range(11)]
    assert statuses[-1] == 429


def test_account_requires_login(client):
    response = client.get("/account")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_forged_session_cookie_is_ignored(client):
    client.set_cookie("gloz_session", "forged-token-value")
    assert client.get("/account").status_code == 302


# ---------------------------------------------------------------- account actions


def test_password_change_signs_out_other_devices(app):
    first = app.test_client()
    second = app.test_client()
    signup(first)
    login(second)
    assert second.get("/account").status_code == 200

    new_password = "quiet-river-bridge-77"
    response = first.post(
        "/account/password",
        data={"csrf_token": csrf(first, "/account"), "current_password": STRONG_PASSWORD, "new_password": new_password, "new_password_confirm": new_password},
    )
    assert response.status_code == 302
    assert first.get("/account").status_code == 200
    assert second.get("/account").status_code == 302


def test_password_change_requires_current_password(client):
    signup(client)
    new_password = "quiet-river-bridge-77"
    response = client.post(
        "/account/password",
        data={"csrf_token": csrf(client, "/account"), "current_password": "wrong-password-123", "new_password": new_password, "new_password_confirm": new_password},
    )
    assert response.status_code == 400


def test_save_and_unsave_listing(client, app):
    signup(client)
    token = csrf(client, "/listings/garden-studio")
    assert client.post("/listings/garden-studio/save", data={"csrf_token": token}).status_code == 302
    assert "Fernhill Garden Studio" in client.get("/account").get_data(as_text=True)
    client.post("/listings/garden-studio/save", data={"csrf_token": token})
    assert _db(app).execute("SELECT COUNT(*) FROM saved_listings").fetchone()[0] == 0


def test_save_requires_login(client):
    token = csrf(client, "/login")
    response = client.post("/listings/garden-studio/save", data={"csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_save_unknown_listing_is_404(client):
    signup(client)
    token = csrf(client, "/account")
    assert client.post("/listings/not-real/save", data={"csrf_token": token}).status_code == 404


def test_delete_account_removes_everything(client, app):
    signup(client)
    token = csrf(client, "/account")
    client.post("/listings/garden-studio/save", data={"csrf_token": token})
    assert client.post("/account/delete", data={"csrf_token": token, "confirm": "nope"}).status_code == 302
    assert _db(app).execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    client.post("/account/delete", data={"csrf_token": token, "confirm": "DELETE"})
    db = _db(app)
    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM saved_listings").fetchone()[0] == 0


# ---------------------------------------------------------------- logging


def test_security_log_has_no_personal_data(client, app):
    signup(client)
    client.post("/logout", data={"csrf_token": csrf(client, "/")})
    login(client, password="wrong-password-123")
    log = (app.config["LOG_DIR"] / "security.jsonl").read_text()
    assert "login_failed" in log
    assert "ana@example.com" not in log
    assert STRONG_PASSWORD not in log
    assert "127.0.0.1" not in log
