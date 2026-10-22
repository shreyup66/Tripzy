from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow
from app.models.user import User


class FriendGroup(Base):
    __tablename__ = "friend_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    members: Mapped[list["FriendGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", passive_deletes=True
    )


class FriendGroupMember(Base):
    __tablename__ = "friend_group_members"

    group_id: Mapped[int] = mapped_column(ForeignKey("friend_groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    group: Mapped[FriendGroup] = relationship(back_populates="members")
    user: Mapped[User] = relationship()
