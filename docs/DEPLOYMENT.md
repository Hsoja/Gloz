# Deployment

A minimal production setup on a Linux server: Gunicorn serves the app on localhost and Caddy handles HTTPS in front of it.

## 1. Install

```bash
git clone https://github.com/Hsoja/Gloz.git /opt/gloz
cd /opt/gloz
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
```

## 2. Configure

Create `/opt/gloz/.env` with production values, readable only by the service user:

```bash
GLOZ_ENV=production
SECRET_KEY=<new random value, 48+ characters>
IP_HASH_SALT=<another random value>
TRUSTED_PROXIES=127.0.0.1
```

```bash
chmod 600 /opt/gloz/.env
```

Never reuse development secrets in production.

## 3. Run Gunicorn

```bash
.venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 1 --threads 4 wsgi:app
```

Use **one worker** while the rate limiter is in memory, so limits are shared by every request. Bind to `127.0.0.1` so the app is only reachable through Caddy. Run it as a systemd service with a dedicated, non-root user.

## 4. Put Caddy in front

Copy `deploy/Caddyfile`, replace `gloz.example.com` with your domain and reload Caddy. It obtains the TLS certificate automatically, hides the `Server` header and blocks hidden files such as `/.env` or `/.git/config`.

## 5. Check before announcing

- [ ] `https://your-domain/health` returns `{"status": "ok"}`
- [ ] `/.env`, `/.git/config`, `/admin` and `/docs` return 404
- [ ] Response headers include `Content-Security-Policy`, `Strict-Transport-Security` and `X-Frame-Options`
- [ ] Cookies are named `__Host-gloz_session` and `__Host-gloz_csrf` and marked `Secure`
- [ ] `logs/` and `instance/` are not inside any folder Caddy serves
- [ ] Daily backup of `instance/gloz.sqlite3`, with a tested restore
