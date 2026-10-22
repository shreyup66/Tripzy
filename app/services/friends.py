from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.errors import AppError, not_found
from app.models import FriendGroup, FriendGroupMember, Friendship, User


def _pair_clause(a: int, b: int):
    return or_(
        and_(Friendship.requester_id == a, Friendship.recipient_id == b),
        and_(Friendship.requester_id == b, Friendship.recipient_id == a),
    )


def get_relationship(db: Session, a: int, b: int) -> Friendship | None:
    return db.scalar(select(Friendship).where(_pair_clause(a, b)))


def are_friends(db: Session, a: int, b: int) -> bool:
    rel = get_relationship(db, a, b)
    return rel is not None and rel.status == "accepted"


def friend_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(
        select(Friendship.requester_id, Friendship.recipient_id).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.recipient_id == user_id),
        )
    )
    return {r if r != user_id else q for r, q in rows}


def list_friends(db: Session, user: User) -> list[User]:
    ids = friend_ids(db, user.id)
    if not ids:
        return []
    return list(db.scalars(select(User).where(User.id.in_(ids)).order_by(User.display_name, User.id)))


def serialize_request(fr: Friendship) -> dict:
    return {
        "id": fr.id,
        "status": fr.status,
        "requester": fr.requester.public(),
        "recipient": fr.recipient.public(),
        "created_at": fr.created_at.isoformat(),
        "updated_at": fr.updated_at.isoformat(),
    }


def list_requests(db: Session, user: User, direction: str) -> list[Friendship]:
    column = Friendship.recipient_id if direction == "incoming" else Friendship.requester_id
    return list(
        db.scalars(
            select(Friendship).where(column == user.id, Friendship.status == "pending").order_by(Friendship.created_at.desc())
        )
    )


def search_users(db: Session, user: User, q: str, limit: int = 20) -> list[dict]:
    escaped = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    users = db.scalars(
        select(User)
        .where(
            User.id != user.id,
            or_(User.email.like(pattern, escape="\\"), User.display_name.ilike(pattern, escape="\\")),
        )
        .order_by(User.display_name, User.id)
        .limit(limit)
    )
    results = []
    for other in users:
        rel = get_relationship(db, user.id, other.id)
        relationship, request_id = "none", None
        if rel and rel.status == "accepted":
            relationship = "friend"
        elif rel and rel.status == "pending":
            relationship = "outgoing" if rel.requester_id == user.id else "incoming"
            request_id = rel.id
        results.append({**other.public(), "relationship": relationship, "request_id": request_id})
    return results


def send_request(db: Session, user: User, recipient_id: int) -> Friendship:
    if recipient_id == user.id:
        raise AppError(400, "You can't send a friend request to yourself", "SELF_FRIEND_REQUEST")
    if db.get(User, recipient_id) is None:
        raise not_found("User")
    rel = get_relationship(db, user.id, recipient_id)
    if rel is None:
        rel = Friendship(requester_id=user.id, recipient_id=recipient_id, status="pending")
        db.add(rel)
    elif rel.status == "accepted":
        raise AppError(409, "You are already friends", "ALREADY_FRIENDS")
    elif rel.status == "pending" and rel.requester_id == user.id:
        raise AppError(409, "Friend request already sent", "DUPLICATE_REQUEST")
    elif rel.status == "pending":
        # They already asked us: treat our request as acceptance.
        rel.status = "accepted"
    else:
        # A rejected/cancelled request is reused so each pair keeps a single row.
        rel.requester_id, rel.recipient_id, rel.status = user.id, recipient_id, "pending"
    db.commit()
    db.refresh(rel)
    return rel


def _get_request(db: Session, request_id: int) -> Friendship:
    rel = db.get(Friendship, request_id)
    if rel is None:
        raise not_found("Friend request")
    return rel


def respond(db: Session, user: User, request_id: int, accept: bool) -> Friendship:
    rel = _get_request(db, request_id)
    if rel.recipient_id != user.id:
        # Don't reveal requests that belong to someone else.
        if rel.requester_id != user.id:
            raise not_found("Friend request")
        raise AppError(403, "Only the recipient can respond to this request", "FORBIDDEN")
    if rel.status != "pending":
        raise AppError(400, f"This request is already {rel.status}", "INVALID_REQUEST_STATE")
    rel.status = "accepted" if accept else "rejected"
    db.commit()
    return rel


def cancel(db: Session, user: User, request_id: int) -> None:
    rel = _get_request(db, request_id)
    if rel.requester_id != user.id:
        if rel.recipient_id != user.id:
            raise not_found("Friend request")
        raise AppError(403, "Only the sender can cancel this request", "FORBIDDEN")
    if rel.status != "pending":
        raise AppError(400, f"This request is already {rel.status}", "INVALID_REQUEST_STATE")
    rel.status = "cancelled"
    db.commit()


def unfriend(db: Session, user: User, other_id: int) -> None:
    rel = get_relationship(db, user.id, other_id)
    if rel is None or rel.status != "accepted":
        raise not_found("Friend")
    db.delete(rel)
    # Friend groups only contain friends, so drop each user from the other's groups.
    for owner, member in ((user.id, other_id), (other_id, user.id)):
        group_ids = select(FriendGroup.id).where(FriendGroup.owner_id == owner)
        db.execute(
            delete(FriendGroupMember).where(
                FriendGroupMember.group_id.in_(group_ids), FriendGroupMember.user_id == member
            )
        )
    db.commit()
