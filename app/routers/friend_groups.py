from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, verify_csrf
from app.models import User
from app.schemas.social import GroupIn, GroupMemberIn
from app.services import groups as svc

router = APIRouter(prefix="/api/friend-groups", tags=["friend groups"], dependencies=[Depends(verify_csrf)])


@router.get("")
def list_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [svc.serialize_group(g) for g in svc.list_groups(db, user)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_group(data: GroupIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_group(svc.create_group(db, user, data.name))


@router.get("/{group_id}")
def get_group(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_group(svc.get_owned_group(db, user, group_id))


@router.patch("/{group_id}")
def rename_group(group_id: int, data: GroupIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_group(svc.rename_group(db, user, group_id, data.name))


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.delete_group(db, user, group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{group_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(group_id: int, data: GroupMemberIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.serialize_group(svc.add_member(db, user, group_id, data.user_id))


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(group_id: int, user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.remove_member(db, user, group_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
