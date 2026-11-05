# Security model

How Gloz is protected and how to keep it that way. Current audit results are in [SECURITY_REPORT.md](../SECURITY_REPORT.md).

## Reporting a vulnerability

Please don't open a public issue for security problems. Use GitHub's **Report a vulnerability** button (Security tab of the repository) to send a private report.

## Threat model (STRIDE)

| Asset | Threat | Main control |
| --- | --- | --- |
| User accounts | Credential stuffing, brute force (Spoofing) | Argon2id, rate limits, progressive lock per account and per IP, identical errors for unknown email and wrong password |
| Sessions | Theft or fixation (Spoofing) | Random 256-bit tokens stored hashed, `HttpOnly` + `Secure` + `SameSite=Strict` cookies, new token at every log-in, revocation on log-out and password change |
| Account actions | Forged requests from other sites (Tampering) | Double-submit CSRF token on every `POST`, origin check, `SameSite=Strict` |
| Pages | Cross-site scripting (Tampering) | Jinja2 auto-escaping, no inline scripts, CSP `script-src 'self'`, no `innerHTML` in JavaScript |
| Database | SQL injection (Tampering, Information disclosure) | Parameterized queries only, allow-listed filters, strict validation |
| Personal data | Leaks through logs or errors (Information disclosure) | Generic error pages with a request id, logs with salted IP hashes and no emails or passwords |
| Availability | Floods and huge requests (Denial of service) | Per-route rate limits, 16 KB body limit, 429 and 413 responses |
| Privileges | Hidden routes or admin modes (Elevation of privilege) | No admin role or default accounts, debug off, explicit route list enforced by tests |

**Trust boundaries:** browser → Caddy → Gunicorn/Flask → SQLite. Everything that comes from the browser (forms, query strings, cookies, headers) is untrusted.

## Controls and where they live

- **Fail-closed configuration:** `app/config.py`
- **Headers, CSRF, rate limits, security log:** `app/security.py`
- **Validation:** `app/validation.py`
- **Authentication, sessions and lockout:** `app/auth.py`
- **Database access:** `app/db.py`
- **HTTPS and proxy:** `deploy/Caddyfile`
- **Regression tests for every control:** `tests/`

## Secrets

- Secrets live only in `.env` (ignored by Git). `.env.example` contains no values.
- Use a different `SECRET_KEY` and `IP_HASH_SALT` for each environment.
- `scripts/scan_exposed_files.sh` and Gitleaks run in CI to catch secrets or data files before they reach `main`.

### Rotating keys

1. Generate new values with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. Update `.env` on the server and restart Gunicorn.
3. Rotating `SECRET_KEY` only discards pending flash messages. Rotating `IP_HASH_SALT` makes new log entries uncorrelatable with old ones; that is expected.
4. To sign everyone out, run `DELETE FROM sessions;` on the database.

Rotate every 90 days, or immediately if a secret may have been exposed.

## If something goes wrong

1. **Contain:** take the site offline or block the source in Caddy.
2. **Close access:** rotate secrets and delete all rows in `sessions`.
3. **Investigate:** check `logs/security.jsonl` using the request id from the error page.
4. **Fix:** patch the cause and add a test that reproduces it.
5. **Record:** add the finding to `SECURITY_REPORT.md`.

Never rewrite Git history to hide an exposed secret without rotating it first: once pushed to a public repository, assume it has been copied.

## Security log

`logs/security.jsonl`, one JSON object per line, rotated at 5 MB with 5 backups. Events: `signup`, `signup_duplicate`, `login_ok`, `login_failed`, `login_locked`, `logout`, `password_changed`, `password_change_failed`, `account_deleted`, `csrf_rejected`, `rate_limited`. Each event has a timestamp, request id, path and a salted hash of the IP.
