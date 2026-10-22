from pydantic import Field

from app.schemas.common import Strict, text


class FriendRequestIn(Strict):
    recipient_id: int


class GroupIn(Strict):
    name: text(100)


class GroupMemberIn(Strict):
    user_id: int


class TripMemberIn(Strict):
    user_id: int | None = None
    email: str | None = Field(default=None, max_length=254)
