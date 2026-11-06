"""The route list is explicit on purpose: a new route that isn't listed here fails the build."""

EXPECTED_ROUTES = {
    ("/", "GET"),
    ("/about", "GET"),
    ("/health", "GET"),
    ("/listings", "GET"),
    ("/listings/<listing_id>", "GET"),
    ("/listings/<listing_id>/save", "POST"),
    ("/privacy", "GET"),
    ("/terms", "GET"),
    ("/signup", "GET"),
    ("/signup", "POST"),
    ("/login", "GET"),
    ("/login", "POST"),
    ("/logout", "POST"),
    ("/account", "GET"),
    ("/account/password", "POST"),
    ("/account/delete", "POST"),
    ("/static/<path:filename>", "GET"),
}


def test_only_expected_routes_exist(app):
    found = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods - {"HEAD", "OPTIONS"}
    }
    assert found == EXPECTED_ROUTES


def test_security_headers_present(client):
    response = client.get("/")
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    # HSTS is only sent in production (behind HTTPS).
    assert "Strict-Transport-Security" not in response.headers


def test_no_inline_scripts_or_styles(client):
    for path in ["/", "/listings", "/listings/pavilion-house", "/login", "/signup", "/about"]:
        html = client.get(path).get_data(as_text=True)
        assert "<script>" not in html and "<script " not in html.replace('<script src="/static/js/gloz.js" defer>', "")
        assert " style=" not in html
        assert "onclick" not in html and "onerror" not in html


def test_debug_is_off(app):
    assert app.debug is False


def test_sensitive_paths_are_404(client):
    for path in ["/.env", "/.git/config", "/admin", "/console", "/docs", "/static/../app/config.py"]:
        assert client.get(path).status_code == 404


def test_unknown_page_uses_generic_error(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    body = response.get_data(as_text=True)
    assert "This page doesn&#39;t exist" in body or "This page doesn't exist" in body
    assert "Traceback" not in body


def test_production_mode_hardening(tmp_path):
    import secrets as _secrets

    from app import create_app

    prod = create_app(
        {
            "GLOZ_ENV": "production",
            "SECRET_KEY": _secrets.token_urlsafe(48),
            "IP_HASH_SALT": _secrets.token_urlsafe(24),
            "DATABASE_PATH": str(tmp_path / "prod.sqlite3"),
            "LOG_DIR": str(tmp_path / "logs"),
        }
    )
    client = prod.test_client()
    response = client.get("/login", base_url="https://localhost")
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
    cookie = next(h for h in response.headers.getlist("Set-Cookie") if h.startswith("__Host-gloz_csrf="))
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert prod.debug is False
