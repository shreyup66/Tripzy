from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, verify_csrf
from app.models import User
from app.schemas.auth import AccountUpdateIn, LoginIn, SignupIn
from app.security import ensure_csrf_token, start_session
from app.services import auth as auth_service

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/auth/csrf")
def csrf_token(request: Request):
    return {"csrf_token": ensure_csrf_token(request)}


# Signup and login create the session, so there is no CSRF token to check yet.
@router.post("/auth/signup", status_code=status.HTTP_201_CREATED)
def signup(data: SignupIn, request: Request, db: Session = Depends(get_db)):
    user = auth_service.signup(db, data)
    token = start_session(request, user.id)
    return {"user": user.public(), "csrf_token": token}


@router.post("/auth/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    client = request.client.host if request.client else "unknown"
    user = auth_service.authenticate(db, data, client)
    token = start_session(request, user.id)
    return {"user": user.public(), "csrf_token": token}


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_csrf)])
def logout(request: Request):
    request.session.clear()


@router.get("/account")
def get_account(user: User = Depends(get_current_user)):
    return {**user.public(), "created_at": user.created_at.isoformat()}


@router.patch("/account", dependencies=[Depends(verify_csrf)])
def update_account(data: AccountUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = auth_service.update_account(db, user, data)
    return {**user.public(), "created_at": user.created_at.isoformat()}
