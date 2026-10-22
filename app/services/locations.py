import asyncio
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, not_found
from app.models import SavedLocation, Trip, User
from app.providers.places import PlacesProvider, PlacesProviderError, PlacesProviderTimeout
from app.schemas.locations import SavedLocationIn


def safe_url(url: str | None) -> str | None:
    """Only keep absolute http(s) URLs; never trust provider/client URLs as markup."""
    if not url:
        return None
    parsed = urlparse(url)
    return url if parsed.scheme in ("http", "https") and parsed.netloc else None


def validate_coordinates(latitude: float | None, longitude: float | None) -> None:
    if (latitude is None) != (longitude is None):
        raise AppError(422, "Provide both latitude and longitude", "INVALID_COORDINATES", "latitude")
    if latitude is not None and not -90 <= latitude <= 90:
        raise AppError(422, "Latitude must be between -90 and 90", "INVALID_COORDINATES", "latitude")
    if longitude is not None and not -180 <= longitude <= 180:
        raise AppError(422, "Longitude must be between -180 and 180", "INVALID_COORDINATES", "longitude")


async def suggest(
    provider: PlacesProvider,
    trip: Trip,
    query: str | None,
    latitude: float | None,
    longitude: float | None,
    limit: int,
) -> dict:
    validate_coordinates(latitude, longitude)
    search = (query or "").strip() or trip.destination
    try:
        raw = await asyncio.wait_for(
            provider.search_popular_places(query=search, latitude=latitude, longitude=longitude, limit=limit),
            timeout=20,
        )
    except (TimeoutError, PlacesProviderTimeout):
        err = PlacesProviderTimeout()
        raise AppError(err.status_code, err.message, err.code) from None
    except PlacesProviderError as err:
        raise AppError(err.status_code, err.message, err.code) from None

    saved_ids = {loc.provider_place_id for loc in trip.saved_locations if loc.provider_place_id}
    results = []
    for place in raw[:limit]:
        if not place.get("name"):
            continue
        results.append(
            {
                "provider_place_id": place.get("provider_place_id"),
                "name": str(place["name"])[:200],
                "category": place.get("category"),
                "address": place.get("address"),
                "rating": place.get("rating"),
                "provider_url": safe_url(place.get("provider_url")),
                "saved": place.get("provider_place_id") in saved_ids,
            }
        )
    return {
        "query": search,
        "near_me": latitude is not None,
        "source": provider.name,
        "demo": provider.demo,
        "attribution": provider.attribution,
        "results": results,
    }


def serialize_location(loc: SavedLocation) -> dict:
    return {
        "id": loc.id,
        "trip_id": loc.trip_id,
        "provider_place_id": loc.provider_place_id,
        "name": loc.name,
        "category": loc.category,
        "address": loc.address,
        "provider_url": loc.provider_url,
        "added_by": loc.added_by,
        "created_at": loc.created_at.isoformat(),
    }


def list_saved(db: Session, trip: Trip) -> list[SavedLocation]:
    return list(
        db.scalars(
            select(SavedLocation).where(SavedLocation.trip_id == trip.id).order_by(SavedLocation.created_at, SavedLocation.id)
        )
    )


def save(db: Session, trip: Trip, user: User, data: SavedLocationIn) -> SavedLocation:
    if data.provider_place_id and any(loc.provider_place_id == data.provider_place_id for loc in trip.saved_locations):
        raise AppError(409, "This place is already saved to the trip", "DUPLICATE_LOCATION")
    if data.provider_url and not safe_url(data.provider_url):
        raise AppError(422, "Provider link must be an http(s) URL", "INVALID_URL", "provider_url")
    # Coordinates are deliberately not persisted (spec §6.6).
    loc = SavedLocation(
        trip_id=trip.id,
        provider_place_id=data.provider_place_id or None,
        name=data.name,
        category=data.category or None,
        address=data.address or None,
        provider_url=data.provider_url or None,
        added_by=user.id,
    )
    db.add(loc)
    db.commit()
    return loc


def remove(db: Session, trip: Trip, location_id: int) -> None:
    loc = db.get(SavedLocation, location_id)
    if loc is None or loc.trip_id != trip.id:
        raise not_found("Saved location")
    db.delete(loc)
    db.commit()
