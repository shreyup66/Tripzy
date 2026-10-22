from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow
from app.models.user import User

FRIENDSHIP_STATUSES = ("pending", "accepted", "rejected", "cancelled")


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("requester_id <> recipient_id", name="ck_friendship_not_self"),
        CheckConstraint(f"status IN {FRIENDSHIP_STATUSES}", name="ck_friendship_status"),
        Index("ix_friendships_recipient_status", "recipient_id", "status"),
        Index("ix_friendships_requester_status", "requester_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])


# One row per pair of users, whichever direction the request went.
Index(
    "uq_friendships_pair",
    func.min(Friendship.requester_id, Friendship.recipient_id),
    func.max(Friendship.requester_id, Friendship.recipient_id),
    unique=True,
)
