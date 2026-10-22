from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow
from app.models.user import User


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date", name="ck_trip_dates"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship()
    members: Mapped[list["TripMember"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", passive_deletes=True
    )
    expenses: Mapped[list["Expense"]] = relationship(  # noqa: F821
        back_populates="trip", cascade="all, delete-orphan", passive_deletes=True
    )
    saved_locations: Mapped[list["SavedLocation"]] = relationship(  # noqa: F821
        back_populates="trip", cascade="all, delete-orphan", passive_deletes=True
    )

    def member_ids(self) -> set[int]:
        return {m.user_id for m in self.members}


class TripMember(Base):
    __tablename__ = "trip_members"
    __table_args__ = (CheckConstraint("role IN ('owner', 'member')", name="ck_trip_member_role"),)

    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(10), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    trip: Mapped[Trip] = relationship(back_populates="members")
    user: Mapped[User] = relationship()
