from datetime import date

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.errors import AppError, forbidden, not_found
from app.models import Expense, ExpenseShare, Trip, TripMember, User
from app.schemas.trips import TripCreateIn, TripUpdateIn
from app.services.auth import get_user_by_email


def _check_dates(start: date | None, end: date | None) -> None:
    if start and end and end < start:
        raise AppError(422, "End date can't be earlier than the start date", "INVALID_DATES", "end_date")


def get_trip_for_member(db: Session, trip_id: int, user: User) -> Trip:
    """Non-members get 404 so trip IDs can't be probed."""
    trip = db.get(Trip, trip_id)
    if trip is None or user.id not in trip.member_ids():
        raise not_found("Trip")
    return trip


def get_trip_for_owner(db: Session, trip_id: int, user: User) -> Trip:
    trip = get_trip_for_member(db, trip_id, user)
    if trip.owner_id != user.id:
        raise forbidden("Only the trip owner can do that")
    return trip


def serialize_member(m: TripMember) -> dict:
    return {**m.user.public(), "role": m.role, "joined_at": m.joined_at.isoformat()}


def serialize_trip(trip: Trip, user: User) -> dict:
    members = sorted(trip.members, key=lambda m: (m.role != "owner", m.user.display_name.lower(), m.user_id))
    return {
        "id": trip.id,
        "name": trip.name,
        "destination": trip.destination,
        "description": trip.description,
        "start_date": trip.start_date.isoformat() if trip.start_date else None,
        "end_date": trip.end_date.isoformat() if trip.end_date else None,
        "owner": trip.owner.public(),
        "is_owner": trip.owner_id == user.id,
        "members": [serialize_member(m) for m in members],
        "member_count": len(members),
        "created_at": trip.created_at.isoformat(),
        "updated_at": trip.updated_at.isoformat(),
    }


def list_trips(db: Session, user: User) -> list[Trip]:
    return list(
        db.scalars(
            select(Trip)
            .join(TripMember, TripMember.trip_id == Trip.id)
            .where(TripMember.user_id == user.id)
            .order_by(Trip.created_at.desc(), Trip.id.desc())
        )
    )


def create_trip(db: Session, user: User, data: TripCreateIn) -> Trip:
    _check_dates(data.start_date, data.end_date)
    extra_ids = sorted(set(data.member_ids) - {user.id})
    if extra_ids:
        found = set(db.scalars(select(User.id).where(User.id.in_(extra_ids))))
        if missing := set(extra_ids) - found:
            raise AppError(422, f"Unknown user ID(s): {sorted(missing)}", "UNKNOWN_MEMBER", "member_ids")
    trip = Trip(
        owner_id=user.id,
        name=data.name,
        destination=data.destination,
        description=data.description or None,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    # Owner membership is created in the same transaction as the trip.
    trip.members.append(TripMember(user_id=user.id, role="owner"))
    trip.members.extend(TripMember(user_id=uid, role="member") for uid in extra_ids)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def update_trip(db: Session, user: User, trip_id: int, data: TripUpdateIn) -> Trip:
    trip = get_trip_for_owner(db, trip_id, user)
    fields = data.model_fields_set
    for name in ("name", "destination"):
        if name in fields:
            value = getattr(data, name)
            if value is None:
                raise AppError(422, f"{name.capitalize()}: This field is required", "VALIDATION_ERROR", name)
            setattr(trip, name, value)
    if "description" in fields:
        trip.description = data.description or None
    start = data.start_date if "start_date" in fields else trip.start_date
    end = data.end_date if "end_date" in fields else trip.end_date
    _check_dates(start, end)
    trip.start_date, trip.end_date = start, end
    db.commit()
    db.refresh(trip)
    return trip


def delete_trip(db: Session, user: User, trip_id: int) -> None:
    trip = get_trip_for_owner(db, trip_id, user)
    # FK cascades remove memberships, expenses, shares and saved locations in one transaction.
    db.delete(trip)
    db.commit()


def add_member(db: Session, user: User, trip_id: int, member_id: int | None, email: str | None) -> TripMember:
    trip = get_trip_for_owner(db, trip_id, user)
    if member_id is not None:
        new_user = db.get(User, member_id)
    elif email and email.strip():
        new_user = get_user_by_email(db, email)
    else:
        raise AppError(422, "Choose a user to add", "VALIDATION_ERROR", "user_id")
    if new_user is None:
        raise AppError(404, "No Tripzy user found with that ID or email", "USER_NOT_FOUND", "email" if email else "user_id")
    if new_user.id in trip.member_ids():
        raise AppError(409, f"{new_user.display_name} is already a member of this trip", "DUPLICATE_MEMBER")
    member = TripMember(user_id=new_user.id, role="member")
    trip.members.append(member)
    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, user: User, trip_id: int, member_id: int) -> None:
    trip = get_trip_for_owner(db, trip_id, user)
    if member_id == trip.owner_id:
        raise AppError(400, "The owner can't be removed. Delete the trip instead.", "OWNER_CANNOT_LEAVE")
    member = db.get(TripMember, (trip.id, member_id))
    if member is None:
        raise not_found("Trip member")
    has_expenses = db.scalar(
        select(
            exists().where(
                Expense.trip_id == trip.id,
                or_(
                    Expense.payer_id == member_id,
                    Expense.id.in_(select(ExpenseShare.expense_id).where(ExpenseShare.user_id == member_id)),
                ),
            )
        )
    )
    if has_expenses:
        raise AppError(
            409,
            f"{member.user.display_name} is part of expenses on this trip. Delete those expenses first.",
            "MEMBER_HAS_EXPENSES",
        )
    trip.members.remove(member)
    db.commit()
