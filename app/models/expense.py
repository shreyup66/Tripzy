from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow
from app.models.trip import Trip
from app.models.user import User


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("total_minor > 0", name="ck_expense_positive"),
        CheckConstraint("split_method IN ('equal', 'custom')", name="ck_expense_split_method"),
        Index("ix_expenses_trip_created", "trip_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    payer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(String(200))
    total_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    split_method: Mapped[str] = mapped_column(String(10))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    trip: Mapped[Trip] = relationship(back_populates="expenses")
    payer: Mapped[User] = relationship(foreign_keys=[payer_id])
    shares: Mapped[list["ExpenseShare"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan", passive_deletes=True
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (CheckConstraint("share_minor >= 0", name="ck_share_non_negative"),)

    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, index=True)
    share_minor: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    expense: Mapped[Expense] = relationship(back_populates="shares")
    user: Mapped[User] = relationship()
