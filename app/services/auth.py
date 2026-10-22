import time
from collections import defaultdict, deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import User
from app.schemas.auth import AccountUpdateIn, LoginIn, SignupIn
from app.security import check_password_strength, hash_password, verify_password

MAX_FAILED_LOGINS = 5
FAILED_LOGIN_WINDOW_SECONDS = 15 * 60
_failed_logins: dict[str, deque[float]] = defaultdict(deque)


def reset_login_limits() -> None:
    _failed_logins.clear()


def _recent_failures(key: str) -> deque[float]:
    attempts = _failed_logins[key]
    cutoff = time.monotonic() - FAILED_LOGIN_WINDOW_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    return attempts


def normalise_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalise_email(email)))


def signup(db: Session, data: SignupIn) -> User:
    check_password_strength(data.password)
    email = normalise_email(data.email)
    if get_user_by_email(db, email):
        raise AppError(409, "An account with this email already exists", "EMAIL_TAKEN", "email")
    user = User(display_name=data.display_name, email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return user


def authenticate(db: Session, data: LoginIn, client_key: str) -> User:
    key = f"{client_key}|{normalise_email(data.email)}"
    attempts = _recent_failures(key)
    if len(attempts) >= MAX_FAILED_LOGINS:
        raise AppError(429, "Too many failed sign-in attempts. Try again in a few minutes.", "TOO_MANY_ATTEMPTS")
    user = get_user_by_email(db, data.email)
    if user is None or not verify_password(user.password_hash, data.password):
        attempts.append(time.monotonic())
        raise AppError(401, "Incorrect email or password", "INVALID_CREDENTIALS")
    _failed_logins.pop(key, None)
    return user


def update_account(db: Session, user: User, data: AccountUpdateIn) -> User:
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.email is not None:
        email = normalise_email(data.email)
        if email != user.email:
            existing = get_user_by_email(db, email)
            if existing and existing.id != user.id:
                raise AppError(409, "An account with this email already exists", "EMAIL_TAKEN", "email")
            user.email = email
    if data.new_password:
        if not data.current_password or not verify_password(user.password_hash, data.current_password):
            raise AppError(422, "Current password is incorrect", "INVALID_CURRENT_PASSWORD", "current_password")
        check_password_strength(data.new_password, "new_password")
        user.password_hash = hash_password(data.new_password)
    db.commit()
    return user
