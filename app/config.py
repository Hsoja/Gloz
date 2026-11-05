"""Application settings, loaded only from environment variables.

The configuration is fail-closed: if a required value is missing or unsafe,
the app refuses to start instead of running with a weak default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VALID_ENVS = {"development", "test", "production"}
MIN_SECRET_LENGTH = 32


class ConfigError(RuntimeError):
    """Raised when the environment would make the app unsafe to run."""


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from a local .env file without overriding real env vars."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    env: str
    secret_key: str
    ip_hash_salt: str
    database_path: Path
    log_dir: Path
    session_hours: int
    trusted_proxies: frozenset[str]

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def secure_cookies(self) -> bool:
        # Browsers accept Secure cookies on http://localhost, so this stays on
        # everywhere except the automated test client.
        return self.env != "test"

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix forces Secure, Path=/ and no Domain attribute.
        return "__Host-gloz_session" if self.is_production else "gloz_session"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-gloz_csrf" if self.is_production else "gloz_csrf"


def load_settings(overrides: dict[str, str] | None = None) -> Settings:
    _load_dotenv(BASE_DIR / ".env")
    env_vars = dict(os.environ)
    if overrides:
        env_vars.update(overrides)

    env = env_vars.get("GLOZ_ENV", "production").strip().lower()
    if env not in VALID_ENVS:
        raise ConfigError(f"GLOZ_ENV must be one of {sorted(VALID_ENVS)}")

    secret_key = env_vars.get("SECRET_KEY", "")
    if len(secret_key) < MIN_SECRET_LENGTH:
        raise ConfigError(
            "SECRET_KEY is missing or shorter than 32 characters. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    ip_hash_salt = env_vars.get("IP_HASH_SALT", "")
    if len(ip_hash_salt) < 16:
        raise ConfigError("IP_HASH_SALT is missing or shorter than 16 characters.")
    if ip_hash_salt == secret_key:
        raise ConfigError("IP_HASH_SALT must be different from SECRET_KEY.")

    database_path = Path(env_vars.get("DATABASE_PATH", str(BASE_DIR / "instance" / "gloz.sqlite3")))
    log_dir = Path(env_vars.get("LOG_DIR", str(BASE_DIR / "logs")))

    proxies = frozenset(
        p.strip() for p in env_vars.get("TRUSTED_PROXIES", "").split(",") if p.strip()
    )
    if "*" in proxies or "0.0.0.0/0" in proxies:
        raise ConfigError("TRUSTED_PROXIES cannot be a wildcard.")

    return Settings(
        env=env,
        secret_key=secret_key,
        ip_hash_salt=ip_hash_salt,
        database_path=database_path,
        log_dir=log_dir,
        session_hours=_int("SESSION_HOURS", 12),
        trusted_proxies=proxies,
    )
