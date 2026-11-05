import pytest

from app.config import ConfigError, load_settings

GOOD = {"SECRET_KEY": "s" * 40, "IP_HASH_SALT": "t" * 20, "GLOZ_ENV": "test"}


def settings(**changes):
    values = {**GOOD, **changes}
    return load_settings(values)


def test_valid_settings_load():
    assert settings().env == "test"


@pytest.mark.parametrize("secret", ["", "short", "x" * 31])
def test_refuses_missing_or_short_secret(secret):
    with pytest.raises(ConfigError):
        settings(SECRET_KEY=secret)


def test_refuses_short_salt():
    with pytest.raises(ConfigError):
        settings(IP_HASH_SALT="abc")


def test_refuses_salt_equal_to_secret():
    with pytest.raises(ConfigError):
        settings(SECRET_KEY="k" * 40, IP_HASH_SALT="k" * 40)


def test_refuses_unknown_environment():
    with pytest.raises(ConfigError):
        settings(GLOZ_ENV="debug")


@pytest.mark.parametrize("proxies", ["*", "0.0.0.0/0", "127.0.0.1,*"])
def test_refuses_wildcard_proxies(proxies):
    with pytest.raises(ConfigError):
        settings(TRUSTED_PROXIES=proxies)


def test_defaults_to_production(monkeypatch):
    monkeypatch.delenv("GLOZ_ENV", raising=False)
    values = {k: v for k, v in GOOD.items() if k != "GLOZ_ENV"}
    loaded = load_settings(values)
    assert loaded.is_production
    assert loaded.secure_cookies
    assert loaded.session_cookie_name.startswith("__Host-")
