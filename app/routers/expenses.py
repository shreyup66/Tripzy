from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, verify_csrf
from app.models import User
from app.schemas.expenses import ExpenseIn
from app.services import expenses as svc
from app.services.trips import get_trip_for_member

router = APIRouter(prefix="/api/trips/{trip_id}", tags=["budget"], dependencies=[Depends(verify_csrf)])


@router.get("/expenses")
def list_expenses(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = get_trip_for_member(db, trip_id, user)
    return [svc.serialize_expense(e) for e in svc.list_expenses(db, trip)]


@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(trip_id: int, data: ExpenseIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = get_trip_for_member(db, trip_id, user)
    return svc.serialize_expense(svc.create_expense(db, trip, user, data))


@router.get("/expenses/{expense_id}")
def get_expense(trip_id: int, expense_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = get_trip_for_member(db, trip_id, user)
    return svc.serialize_expense(svc.get_expense(db, trip, expense_id))


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(trip_id: int, expense_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = get_trip_for_member(db, trip_id, user)
    svc.delete_expense(db, trip, expense_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/balances")
def balances(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.compute_balances(db, get_trip_for_member(db, trip_id, user))
