# Architecture

Gloz is a server-rendered Flask application. Pages are HTML generated with Jinja2 templates; JavaScript only adds small enhancements, so every feature works with JavaScript disabled.

## Modules

| Module | Responsibility |
| --- | --- |
| `app/__init__.py` | `create_app()` factory: loads settings, wires the database, security and blueprints, registers generic error pages |
| `app/config.py` | Reads settings from environment variables (and an optional `.env`). Fail-closed: raises `ConfigError` on missing or weak secrets, unknown environments or wildcard proxies |
| `app/db.py` | One SQLite connection per request (`flask.g`), foreign keys on, schema created at startup |
| `app/security.py` | Security headers and CSP, CSRF check, client IP resolution, in-memory rate limiter, JSON security log |
| `app/validation.py` | Validates and normalizes form input: allow-listed fields, length limits, email format, password rules |
| `app/auth.py` | Blueprint `auth`: sign-up, log-in, log-out, account page, password change, account deletion, saving listings, session handling and lockout |
| `app/listings.py` | The sample catalogue (fictional homes) and the filter/sort logic |
| `app/views.py` | Blueprint `main`: home, listings, listing detail, about, privacy, terms, health check |

## Request flow

```
Browser ──HTTPS──▶ Caddy (TLS, headers) ──▶ Gunicorn ──▶ Flask app
                                                         │
             before_request: request id → CSRF check → load user from session cookie
                                                         │
                                  route (rate limit → validation → SQLite)
                                                         │
              after_request: security headers, Cache-Control, CSRF cookie
```

1. `security._before` assigns a request id and, for `POST` requests, verifies that the CSRF cookie matches the hidden form field and that the `Origin`/`Referer` (when present) is the same host.
2. `auth.load_current_user` hashes the session cookie and looks it up in the `sessions` table. If it is valid and not expired, `g.user` is set.
3. The route runs. Routes that change data are `POST` only, rate-limited, and protected with `login_required` where needed.
4. `security._after` adds the security headers and sets the CSRF cookie if a new token was issued.

## Data model

```
users            id, email (unique), display_name, password_hash (Argon2id), created_at
sessions         token_hash (SHA-256, PK), user_id → users, created_at, expires_at
login_failures   key (pseudonymized user or IP), failures, locked_until, updated_at
saved_listings   (user_id → users, listing_id) PK, saved_at
```

Deleting a user cascades to their sessions and saved listings. Listings are not stored in the database: they are fictional demo content kept in `app/listings.py` until there is a way to manage real ones.

## Design decisions

- **Server-side sessions instead of signed cookies.** A random token in an `HttpOnly` cookie, stored hashed, can be revoked: logging out, changing the password or deleting the account invalidates it immediately.
- **No CSS framework or CDN.** The previous version loaded Bootstrap and Font Awesome bundles of unclear origin. The new design uses one stylesheet, an inline SVG icon sprite and self-hosted fonts, which keeps the CSP strict (`'self'` only) and the page light.
- **Filters on the server.** Search parameters are parsed against allow-lists, so invalid values are ignored instead of reaching any logic, and each search has a shareable URL.
- **SQLite.** Enough for a single-instance demo. The rate limiter is in memory for the same reason; scaling to several processes would need Redis and PostgreSQL (see the roadmap).

## Frontend design system

| Token | Value | Use |
| --- | --- | --- |
| Blueprint | `#0F3B82` | Headings, footer, selected states |
| Cobalt | `#1F5FE0` | Buttons, links, focus ring |
| Ink | `#0D1B33` | Body text |
| Slate | `#475A78` | Secondary text |
| Mist / Sky | `#F1F6FD` / `#D8E5F7` | Tinted sections, grid lines, borders |
| Paper | `#FFFFFF` | Background |

Type: **Bricolage Grotesque** for headings and prices, **Instrument Sans** for text. The signature element is the blueprint floor plan in the hero, drawn once when the page loads (skipped when the user prefers reduced motion).
