import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request

from app.errors import AppError

_hasher = PasswordHasher()  # Argon2id with a random salt per hash

CSRF_SESSION_KEY = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def check_password_strength(password: str, field: str = "password") -> None:
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise AppError(
            422, "Password must be at least 8 characters and include a letter and a number", "WEAK_PASSWORD", field
        )


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def start_session(request: Request, user_id: int) -> str:
    """Replace any previous session contents and issue a fresh CSRF token."""
    request.session.clear()
    request.session["user_id"] = user_id
    return ensure_csrf_token(request)
