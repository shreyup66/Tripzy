from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services import friends as friend_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/search")
def search_users(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return friend_service.search_users(db, user, q, limit)
