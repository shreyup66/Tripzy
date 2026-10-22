from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, verify_csrf
from app.models import User
from app.schemas.social import FriendRequestIn
from app.services import friends as svc

router = APIRouter(prefix="/api", tags=["friends"], dependencies=[Depends(verify_csrf)])


@router.get("/friends")
def list_friends(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [f.public() for f in svc.list_friends(db, user)]


@router.delete("/friends/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unfriend(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.unfriend(db, user, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/friend-requests")
def list_requests(
    direction: Literal["incoming", "outgoing"] = Query("incoming"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return [svc.serialize_request(r) for r in svc.list_requests(db, user, direction)]


@router.post("/friend-requests", status_code=status.HTTP_201_CREATED)
def send_request(data: FriendRequestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_request(svc.send_request(db, user, data.recipient_id))


@router.post("/friend-requests/{request_id}/accept")
def accept(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_request(svc.respond(db, user, request_id, accept=True))


@router.post("/friend-requests/{request_id}/reject")
def reject(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_request(svc.respond(db, user, request_id, accept=False))


@router.delete("/friend-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.cancel(db, user, request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
