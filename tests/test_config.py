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


def test_dotenv_ignores_empty_template_lines(tmp_path, monkeypatch):
    from app import config

    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=\nIP_HASH_SALT=\nSECRET_KEY=" + "a" * 40 + "\nIP_HASH_SALT=" + "b" * 20 + "\n")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("IP_HASH_SALT", raising=False)
    config._load_dotenv(env_file)
    import os

    assert os.environ["SECRET_KEY"] == "a" * 40
    assert os.environ["IP_HASH_SALT"] == "b" * 20
