# Security report

**Date:** 2026-11-05 · **Branch:** `feat/restructure-redesign` · **Scope:** full rewrite of the Flask back end and front end, Git history of the public repository.

**Verdict: 🟡 Approved with risks.** No high findings are open. The residual risks below are documented and acceptable for a portfolio demo; they must be addressed before handling real users.

## Tool results

| Check | Result | Notes |
| --- | --- | --- |
| `pytest` (64 tests) | ✅ Pass | Includes abuse cases: no session, CSRF missing/wrong/cross-origin, XSS, SQLi, 413, 429, lockout, route allow-list |
| `pip-audit -r requirements-lock.txt` | ✅ No known vulnerabilities | |
| `bandit --severity-level medium` | ✅ No findings | 5 low-severity B105 false positives: user-facing messages containing the word "password" |
| `semgrep` | ✅ 0 findings | Run locally with 362 rules from the official `semgrep-rules` repository (Flask, Python security, secrets). The registry packs `p/python`, `p/flask`, `p/secrets` could not be downloaded from this environment; CI runs them |
| `gitleaks` (full history, 3 previous commits + working tree) | ✅ No leaks | |
| `scripts/scan_exposed_files.sh` | ✅ Pass | No `.env`, keys, databases or logs tracked; `.gitignore` covers them |
| Browser check (Chromium via Playwright) | ✅ Pass | Sign-up → save homes → account → log-out → failed log-in; no CSP violations; desktop and 390 px mobile |
| OWASP ZAP (DAST) | ⚪ Not verified | No staging deployment yet |

## Findings in the previous version

| ID | Severity | File | Issue | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| G1 | Medium | `gloz.py` | `app.run(debug=True)`: the Werkzeug debugger allows remote code execution if the server is exposed | Debug is always off; `run.py` binds to `127.0.0.1`; production uses Gunicorn | Fixed |
| G2 | Medium | `registrarse.html`, `inicias_secion.html` | Sign-up and log-in forms posted to `#` with no server, validation, password hashing or CSRF protection | Real auth with Argon2id, server-side sessions, CSRF, validation and lockout | Fixed |
| G3 | Low | repo root | Vendored minified Bootstrap and Font Awesome bundles with no version or source recorded | Removed; custom CSS, inline SVG icons and self-hosted OFL fonts with licenses | Fixed |
| G4 | Low | `index.html` | Pages referenced `/static/...` paths that didn't exist; broken markup and links (`register.html`), placeholder navbar content | New template structure; every link and asset is covered by tests | Fixed |
| G5 | Low | `inicias_secion.html` | "Continue with Google / Apple" buttons that did nothing, suggesting an integration that didn't exist | Removed until a real OAuth integration exists | Fixed |
| G6 | Info | Git history | No credentials, keys or personal files found in history | Nothing to rotate | N/A |

## Controls added (checklist)

- [x] Fail-closed configuration: no start without strong `SECRET_KEY` and `IP_HASH_SALT`; default environment is `production`
- [x] No default credentials or admin accounts; debug off everywhere
- [x] Argon2id with automatic rehash; 12-character minimum
- [x] Random session tokens stored as SHA-256; `HttpOnly`, `Secure`, `SameSite=Strict`, `__Host-` prefix in production
- [x] Sessions revoked on log-out, password change (all devices) and account deletion
- [x] Double-submit CSRF token on every `POST`, plus origin check
- [x] Rate limits per route and progressive lockout per account and per IP; identical error for unknown email and wrong password
- [x] Strict validation with allow-listed fields and length limits; 16 KB body limit
- [x] Parameterized SQL only
- [x] CSP `default-src 'self'` with no inline code; HSTS (production), `X-Frame-Options`, `nosniff`, Referrer, Permissions, COOP and CORP headers
- [x] Generic error pages with request id; no stack traces to the client
- [x] Security log in JSON with salted IP hashes; no emails, passwords or tokens
- [x] Explicit route list enforced by tests (detects hidden routes)
- [x] CI with read-only permissions, actions pinned by SHA, Dependabot
- [x] Privacy policy and terms (marked as drafts)
- [x] Images re-encoded without metadata

## Residual risks

| Risk | Severity | Why it's accepted for now | Next step |
| --- | --- | --- | --- |
| Rate limiter is in memory | Low | Single Gunicorn worker in the demo | Redis-backed limiter before scaling |
| No email verification or password reset | Low | Demo accounts with no real data | Add verified email with signed, expiring links |
| No MFA | Low | No privileged roles exist | Add TOTP if agent or admin roles are introduced |
| SQLite | Low | Single instance | PostgreSQL with migrations |
| Legal pages not reviewed by a lawyer | Low | Marked as drafts on the page | Legal review before any real launch |
| Commit author name is public in Git metadata | Info | History already uses GitHub's `noreply` email, so no personal address is exposed | Keep "Keep my email addresses private" enabled on GitHub |
| No DAST scan | Low | No staging environment | Run OWASP ZAP against staging before launch |

## How to reproduce

See [docs/SECURITY.md](docs/SECURITY.md#controls-and-where-they-live) and the commands in the README under *Tests and security checks*.
