import secrets

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models import User
from app.security import CSRF_HEADER, CSRF_SESSION_KEY

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, int):
        return None
    return db.get(User, user_id)


def get_current_user(user: User | None = Depends(get_optional_user)) -> User:
    if user is None:
        raise AppError(401, "Sign in to continue", "NOT_AUTHENTICATED")
    return user


def verify_csrf(request: Request) -> None:
    """Cookie-authenticated mutations must echo the session's CSRF token in a header."""
    if request.method not in UNSAFE_METHODS or "user_id" not in request.session:
        # Signed-out requests carry no authority; protected endpoints reject them with 401.
        return
    expected = request.session.get(CSRF_SESSION_KEY) or ""
    supplied = request.headers.get(CSRF_HEADER) or ""
    if not expected or not secrets.compare_digest(expected, supplied):
        raise AppError(403, "Your session expired. Refresh the page and try again.", "CSRF_FAILED")
