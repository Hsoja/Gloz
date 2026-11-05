"""Strict server-side validation. Client-side checks only help the user; these are the real ones."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,190}\.[A-Za-z]{2,24}$")
MAX_EMAIL = 254
MIN_PASSWORD = 12
MAX_PASSWORD = 128
MAX_NAME = 60


@dataclass
class Result:
    data: dict[str, str] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def _clean_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    # Drop control characters (keeps letters with accents, spaces, punctuation).
    return "".join(ch for ch in value if unicodedata.category(ch)[0] != "C")


def _allowed_fields(form, allowed: set[str]) -> bool:
    return set(form.keys()) <= allowed | {"csrf_token"}


def email(value: str) -> str | None:
    value = value.strip().lower()
    if len(value) > MAX_EMAIL or not EMAIL_RE.fullmatch(value) or ".." in value:
        return None
    return value


def password_problem(password: str, email_value: str = "") -> str | None:
    if len(password) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if len(password) > MAX_PASSWORD:
        return f"Use at most {MAX_PASSWORD} characters."
    if email_value and password.lower() == email_value.lower():
        return "Your password can't be your email."
    if len(set(password)) < 5:
        return "Use a less repetitive password."
    return None


def registration(form) -> Result:
    result = Result()
    if not _allowed_fields(form, {"email", "display_name", "password", "password_confirm"}):
        result.errors["form"] = "Unexpected fields in the form."
        return result

    mail = email(form.get("email", ""))
    if mail is None:
        result.errors["email"] = "Enter a valid email address."
    else:
        result.data["email"] = mail

    name = _clean_text(form.get("display_name", ""))
    if not name or len(name) > MAX_NAME:
        result.errors["display_name"] = f"Enter a name between 1 and {MAX_NAME} characters."
    else:
        result.data["display_name"] = name

    password = form.get("password", "")
    problem = password_problem(password, mail or "")
    if problem:
        result.errors["password"] = problem
    elif password != form.get("password_confirm", ""):
        result.errors["password_confirm"] = "The passwords don't match."
    else:
        result.data["password"] = password
    return result


def login(form) -> Result:
    result = Result()
    if not _allowed_fields(form, {"email", "password"}):
        result.errors["form"] = "Unexpected fields in the form."
        return result
    mail = email(form.get("email", ""))
    password = form.get("password", "")
    if mail is None or not password or len(password) > MAX_PASSWORD:
        result.errors["form"] = "Email or password is incorrect."
        return result
    result.data = {"email": mail, "password": password}
    return result


def password_change(form, email_value: str) -> Result:
    result = Result()
    if not _allowed_fields(form, {"current_password", "new_password", "new_password_confirm"}):
        result.errors["form"] = "Unexpected fields in the form."
        return result
    current = form.get("current_password", "")
    new = form.get("new_password", "")
    if not current or len(current) > MAX_PASSWORD:
        result.errors["current_password"] = "Enter your current password."
    problem = password_problem(new, email_value)
    if problem:
        result.errors["new_password"] = problem
    elif new != form.get("new_password_confirm", ""):
        result.errors["new_password_confirm"] = "The passwords don't match."
    elif new == current:
        result.errors["new_password"] = "Choose a password you haven't used here."
    if result.ok:
        result.data = {"current_password": current, "new_password": new}
    return result
