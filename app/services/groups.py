from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, not_found
from app.models import FriendGroup, FriendGroupMember, User
from app.services.friends import are_friends


def serialize_group(group: FriendGroup) -> dict:
    members = sorted(group.members, key=lambda m: (m.user.display_name.lower(), m.user_id))
    return {
        "id": group.id,
        "name": group.name,
        "created_at": group.created_at.isoformat(),
        "members": [{**m.user.public(), "added_at": m.added_at.isoformat()} for m in members],
    }


def list_groups(db: Session, user: User) -> list[FriendGroup]:
    return list(
        db.scalars(select(FriendGroup).where(FriendGroup.owner_id == user.id).order_by(FriendGroup.name, FriendGroup.id))
    )


def get_owned_group(db: Session, user: User, group_id: int) -> FriendGroup:
    group = db.get(FriendGroup, group_id)
    if group is None or group.owner_id != user.id:
        raise not_found("Friend group")
    return group


def create_group(db: Session, user: User, name: str) -> FriendGroup:
    group = FriendGroup(owner_id=user.id, name=name)
    db.add(group)
    db.commit()
    return group


def rename_group(db: Session, user: User, group_id: int, name: str) -> FriendGroup:
    group = get_owned_group(db, user, group_id)
    group.name = name
    db.commit()
    return group


def delete_group(db: Session, user: User, group_id: int) -> None:
    db.delete(get_owned_group(db, user, group_id))
    db.commit()


def add_member(db: Session, user: User, group_id: int, member_id: int) -> FriendGroup:
    group = get_owned_group(db, user, group_id)
    if db.get(User, member_id) is None:
        raise not_found("User")
    if not are_friends(db, user.id, member_id):
        raise AppError(422, "You can only add accepted friends to a group", "NOT_A_FRIEND", "user_id")
    if any(m.user_id == member_id for m in group.members):
        raise AppError(409, "This friend is already in the group", "DUPLICATE_GROUP_MEMBER", "user_id")
    group.members.append(FriendGroupMember(user_id=member_id))
    db.commit()
    db.refresh(group)
    return group


def remove_member(db: Session, user: User, group_id: int, member_id: int) -> None:
    group = get_owned_group(db, user, group_id)
    member = db.get(FriendGroupMember, (group.id, member_id))
    if member is None:
        raise not_found("Group member")
    db.delete(member)
    db.commit()
