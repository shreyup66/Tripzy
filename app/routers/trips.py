from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, verify_csrf
from app.models import User
from app.schemas.social import TripMemberIn
from app.schemas.trips import TripCreateIn, TripUpdateIn
from app.services import trips as svc

router = APIRouter(prefix="/api/trips", tags=["trips"], dependencies=[Depends(verify_csrf)])


@router.get("")
def list_trips(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [svc.serialize_trip(t, user) for t in svc.list_trips(db, user)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_trip(data: TripCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_trip(svc.create_trip(db, user, data), user)


@router.get("/{trip_id}")
def get_trip(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_trip(svc.get_trip_for_member(db, trip_id, user), user)


@router.patch("/{trip_id}")
def update_trip(trip_id: int, data: TripUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_trip(svc.update_trip(db, user, trip_id, data), user)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.delete_trip(db, user, trip_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{trip_id}/members")
def list_members(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_trip(svc.get_trip_for_member(db, trip_id, user), user)["members"]


@router.post("/{trip_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(trip_id: int, data: TripMemberIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_member(svc.add_member(db, user, trip_id, data.user_id, data.email))


@router.delete("/{trip_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(trip_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.remove_member(db, user, trip_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
