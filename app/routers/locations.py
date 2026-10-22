from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, verify_csrf
from app.models import User
from app.providers.places import PlacesProvider, get_places_provider
from app.schemas.locations import SavedLocationIn
from app.services import locations as svc
from app.services.trips import get_trip_for_member

router = APIRouter(prefix="/api/trips/{trip_id}/locations", tags=["locations"], dependencies=[Depends(verify_csrf)])


@router.get("/suggestions")
async def suggestions(
    trip_id: int,
    query: str | None = Query(None, max_length=200),
    latitude: float | None = Query(None),
    longitude: float | None = Query(None),
    limit: int = Query(10, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: PlacesProvider = Depends(get_places_provider),
):
    trip = get_trip_for_member(db, trip_id, user)
    return await svc.suggest(provider, trip, query, latitude, longitude, limit)


@router.get("")
def list_locations(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = get_trip_for_member(db, trip_id, user)
    return [svc.serialize_location(loc) for loc in svc.list_saved(db, trip)]


@router.post("", status_code=status.HTTP_201_CREATED)
def save_location(trip_id: int, data: SavedLocationIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = get_trip_for_member(db, trip_id, user)
    return svc.serialize_location(svc.save(db, trip, user, data))


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_location(trip_id: int, location_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = get_trip_for_member(db, trip_id, user)
    svc.remove(db, trip, location_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
