import asyncio

from app.models import SavedLocation
from app.providers.places import MockPlacesProvider, PlacesProvider, PlacesProviderRateLimited, get_places_provider
from tests.conftest import create_trip


class EmptyProvider(PlacesProvider):
    name = "empty"

    async def search_popular_places(self, **_kwargs):
        return []


class SlowProvider(PlacesProvider):
    name = "slow"

    async def search_popular_places(self, **_kwargs):
        raise asyncio.TimeoutError


class RateLimitedProvider(PlacesProvider):
    name = "limited"

    async def search_popular_places(self, **_kwargs):
        raise PlacesProviderRateLimited()


class EvilProvider(PlacesProvider):
    name = "evil"

    async def search_popular_places(self, **_kwargs):
        return [{"provider_place_id": "x", "name": "<script>alert(1)</script>", "provider_url": "javascript:alert(1)"}]


class RecordingProvider(MockPlacesProvider):
    def __init__(self):
        self.calls = []

    async def search_popular_places(self, **kwargs):
        self.calls.append(kwargs)
        return await super().search_popular_places(**kwargs)


def use_provider(app, provider):
    app.dependency_overrides[get_places_provider] = lambda: provider


def suggestions(client, trip, **params):
    return client.get(f"/api/trips/{trip['id']}/locations/suggestions", params=params)


def test_suggestions_default_to_trip_destination(alex):
    trip = create_trip(alex)
    r = suggestions(alex, trip)
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "North Goa, India" and body["demo"] is True
    assert "Baga Beach" in [p["name"] for p in body["results"]]
    first = body["results"][0]
    assert {"name", "category", "address", "rating", "provider_url"} <= first.keys()


def test_manual_keyword_search(alex):
    trip = create_trip(alex)
    names = [p["name"] for p in suggestions(alex, trip, query="Jaipur").json()["results"]]
    assert "Hawa Mahal" in names


def test_coordinates_passed_to_provider_and_validated(alex, app):
    provider = RecordingProvider()
    use_provider(app, provider)
    trip = create_trip(alex)
    r = suggestions(alex, trip, latitude=15.5, longitude=73.8)
    assert r.status_code == 200 and r.json()["near_me"] is True
    assert provider.calls[-1]["latitude"] == 15.5 and provider.calls[-1]["longitude"] == 73.8
    assert suggestions(alex, trip, latitude=91, longitude=0).status_code == 422
    assert suggestions(alex, trip, latitude=0, longitude=181).status_code == 422
    assert suggestions(alex, trip, latitude=10).status_code == 422


def test_no_results_is_empty_state(alex, app):
    use_provider(app, EmptyProvider())
    trip = create_trip(alex)
    r = suggestions(alex, trip)
    assert r.status_code == 200 and r.json()["results"] == []


def test_provider_timeout_is_friendly_error(alex, app):
    use_provider(app, SlowProvider())
    trip = create_trip(alex)
    r = suggestions(alex, trip)
    assert r.status_code == 504 and r.json()["code"] == "PLACES_PROVIDER_TIMEOUT"
    assert "try again" in r.json()["detail"].lower()


def test_provider_rate_limit(alex, app):
    use_provider(app, RateLimitedProvider())
    trip = create_trip(alex)
    assert suggestions(alex, trip).status_code == 503


def test_unsafe_provider_urls_dropped(alex, app):
    use_provider(app, EvilProvider())
    trip = create_trip(alex)
    place = suggestions(alex, trip).json()["results"][0]
    assert place["provider_url"] is None
    assert place["name"] == "<script>alert(1)</script>"  # returned as data; the UI renders it as text


def test_save_list_and_remove_location(alex, blair):
    trip = create_trip(alex, blair)
    place = suggestions(alex, trip).json()["results"][0]
    body = {k: place[k] for k in ("provider_place_id", "name", "category", "address", "provider_url")}
    r = blair.post(f"/api/trips/{trip['id']}/locations", json=body)
    assert r.status_code == 201
    loc_id = r.json()["id"]
    assert alex.post(f"/api/trips/{trip['id']}/locations", json=body).status_code == 409
    assert [x["id"] for x in alex.get(f"/api/trips/{trip['id']}/locations").json()] == [loc_id]
    assert suggestions(alex, trip).json()["results"][0]["saved"] is True
    assert alex.delete(f"/api/trips/{trip['id']}/locations/{loc_id}").status_code == 204
    assert alex.get(f"/api/trips/{trip['id']}/locations").json() == []


def test_save_rejects_unsafe_url_and_missing_name(alex):
    trip = create_trip(alex)
    assert alex.post(f"/api/trips/{trip['id']}/locations", json={"name": "X", "provider_url": "javascript:alert(1)"}).status_code == 422
    assert alex.post(f"/api/trips/{trip['id']}/locations", json={"name": ""}).status_code == 422


def test_coordinates_not_persisted(alex, db):
    trip = create_trip(alex)
    alex.post(f"/api/trips/{trip['id']}/locations", json={"name": "Somewhere"})
    loc = db.query(SavedLocation).one()
    assert loc.latitude is None and loc.longitude is None


def test_non_member_cannot_use_locations(alex, casey):
    trip = create_trip(alex)
    assert suggestions(casey, trip).status_code == 404
    assert casey.get(f"/api/trips/{trip['id']}/locations").status_code == 404
    assert casey.post(f"/api/trips/{trip['id']}/locations", json={"name": "X"}).status_code == 404


def test_location_from_other_trip_cannot_be_removed(alex):
    t1, t2 = create_trip(alex), create_trip(alex)
    loc_id = alex.post(f"/api/trips/{t1['id']}/locations", json={"name": "X"}).json()["id"]
    assert alex.delete(f"/api/trips/{t2['id']}/locations/{loc_id}").status_code == 404
