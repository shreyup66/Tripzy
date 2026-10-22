"""Places provider adapter.

Every provider returns normalised place dicts:
    {provider_place_id, name, category, address, rating, provider_url, latitude, longitude}
"""

from functools import lru_cache

import httpx

from app.config import get_settings


class PlacesProviderError(Exception):
    status_code = 502
    code = "PLACES_PROVIDER_ERROR"
    message = "We couldn't load place suggestions right now. Please try again."


class PlacesProviderTimeout(PlacesProviderError):
    status_code = 504
    code = "PLACES_PROVIDER_TIMEOUT"
    message = "The places service took too long to respond. Please try again."


class PlacesProviderRateLimited(PlacesProviderError):
    status_code = 503
    code = "PLACES_PROVIDER_RATE_LIMITED"
    message = "Too many place searches right now. Wait a moment and try again."


class PlacesProvider:
    name = "base"
    demo = False
    attribution: str | None = None

    async def search_popular_places(
        self,
        *,
        query: str,
        latitude: float | None = None,
        longitude: float | None = None,
        limit: int = 10,
    ) -> list[dict]:
        raise NotImplementedError


def _place(pid, name, category, address, rating=None, lat=None, lon=None, url=None) -> dict:
    return {
        "provider_place_id": pid,
        "name": name,
        "category": category,
        "address": address,
        "rating": rating,
        "provider_url": url,
        "latitude": lat,
        "longitude": lon,
    }


_MOCK_DATA: dict[str, list[tuple]] = {
    "goa": [
        ("Baga Beach", "Beach", "Baga, North Goa", 4.4, 15.5553, 73.7517),
        ("Fort Aguada", "Historic fort", "Candolim, North Goa", 4.5, 15.4925, 73.7737),
        ("Basilica of Bom Jesus", "Church / heritage site", "Old Goa", 4.7, 15.5009, 73.9116),
        ("Anjuna Flea Market", "Market", "Anjuna, North Goa", 4.2, 15.5735, 73.7410),
        ("Dudhsagar Falls", "Waterfall", "Sonaulim, South Goa", 4.6, 15.3144, 74.3143),
        ("Chapora Fort", "Historic fort", "Chapora, North Goa", 4.3, 15.6060, 73.7366),
    ],
    "mumbai": [
        ("Gateway of India", "Monument", "Apollo Bandar, Colaba", 4.6, 18.9220, 72.8347),
        ("Marine Drive", "Promenade", "Netaji Subhash Chandra Bose Road", 4.7, 18.9440, 72.8231),
        ("Chhatrapati Shivaji Terminus", "Heritage site", "Fort, Mumbai", 4.6, 18.9398, 72.8355),
        ("Elephanta Caves", "Cave temples", "Gharapuri Island", 4.4, 18.9633, 72.9315),
        ("Sanjay Gandhi National Park", "National park", "Borivali East", 4.4, 19.2147, 72.9106),
    ],
    "pune": [
        ("Shaniwar Wada", "Historic fort", "Shaniwar Peth, Pune", 4.3, 18.5195, 73.8553),
        ("Aga Khan Palace", "Museum", "Kalyani Nagar, Pune", 4.4, 18.5524, 73.9015),
        ("Sinhagad Fort", "Historic fort", "Thoptewadi, Pune", 4.5, 18.3664, 73.7559),
        ("Dagdusheth Halwai Ganpati Temple", "Temple", "Budhwar Peth, Pune", 4.7, 18.5164, 73.8561),
        ("Raja Dinkar Kelkar Museum", "Museum", "Shukrawar Peth, Pune", 4.4, 18.5106, 73.8538),
    ],
    "delhi": [
        ("Red Fort", "Historic fort", "Chandni Chowk, Delhi", 4.5, 28.6562, 77.2410),
        ("Qutub Minar", "Monument", "Mehrauli, Delhi", 4.5, 28.5245, 77.1855),
        ("India Gate", "Monument", "Kartavya Path, New Delhi", 4.6, 28.6129, 77.2295),
        ("Humayun's Tomb", "Heritage site", "Nizamuddin, Delhi", 4.6, 28.5933, 77.2507),
        ("Lotus Temple", "Temple", "Kalkaji, New Delhi", 4.5, 28.5535, 77.2588),
    ],
    "jaipur": [
        ("Amber Fort", "Historic fort", "Amer, Jaipur", 4.6, 26.9855, 75.8513),
        ("Hawa Mahal", "Palace", "Badi Choupad, Jaipur", 4.4, 26.9239, 75.8267),
        ("City Palace", "Palace / museum", "Tulsi Marg, Jaipur", 4.5, 26.9258, 75.8237),
        ("Jantar Mantar", "Observatory", "Gangori Bazaar, Jaipur", 4.5, 26.9248, 75.8246),
        ("Nahargarh Fort", "Historic fort", "Krishna Nagar, Jaipur", 4.4, 26.9373, 75.8155),
    ],
}

_GENERIC = [
    ("Old Town", "Neighbourhood"),
    ("City Museum", "Museum"),
    ("Central Market", "Market"),
    ("Riverside Park", "Park"),
    ("Viewpoint", "Viewpoint"),
]


def _osm_search_url(name: str, area: str) -> str:
    return str(httpx.URL("https://www.openstreetmap.org/search", params={"query": f"{name}, {area}"}))


class MockPlacesProvider(PlacesProvider):
    """Deterministic offline provider for development and tests. Results are labelled as demo data."""

    name = "mock"
    demo = True

    async def search_popular_places(self, *, query, latitude=None, longitude=None, limit=10):
        q = (query or "").strip().lower()
        for key, places in _MOCK_DATA.items():
            if key in q:
                return [
                    _place(f"mock-{key}-{i}", n, c, a, r, la, lo, _osm_search_url(n, a))
                    for i, (n, c, a, r, la, lo) in enumerate(places[:limit], start=1)
                ]
        if latitude is not None and longitude is not None:
            area = f"near {latitude:.2f}, {longitude:.2f}"
            return [
                _place(f"mock-near-{latitude:.2f}-{longitude:.2f}-{i}", f"Nearby {n}", c, area, None, latitude, longitude)
                for i, (n, c) in enumerate(_GENERIC[:limit], start=1)
            ]
        if not q:
            return []
        title = query.strip().title()
        slug = "-".join(q.split())[:60]
        return [
            _place(f"mock-{slug}-{i}", f"{title} {n}", c, title, None, None, None, _osm_search_url(f"{title} {n}", title))
            for i, (n, c) in enumerate(_GENERIC[:limit], start=1)
        ]


class OpenStreetMapPlacesProvider(PlacesProvider):
    """Live data from OpenStreetMap: Nominatim geocodes the destination, Overpass finds attractions.

    No API key needed; respect the usage policies (identify the app, keep request volume low).
    """

    name = "osm"
    attribution = "© OpenStreetMap contributors"
    NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
    # Public Overpass servers are often busy, so try a mirror before giving up.
    OVERPASS_URLS = (
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    )

    def __init__(self, timeout: float, user_agent: str):
        self.timeout = timeout
        self.user_agent = user_agent

    @staticmethod
    def _check(response: httpx.Response) -> None:
        if response.status_code == 429:
            raise PlacesProviderRateLimited()
        if response.status_code >= 400:
            raise PlacesProviderError()

    async def search_popular_places(self, *, query, latitude=None, longitude=None, limit=10):
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": self.user_agent}) as client:
                radius = 5000
                if latitude is None or longitude is None:
                    resp = await client.get(self.NOMINATIM_URL, params={"q": query, "format": "jsonv2", "limit": 1})
                    self._check(resp)
                    hits = resp.json()
                    if not hits:
                        return []
                    latitude, longitude = float(hits[0]["lat"]), float(hits[0]["lon"])
                    radius = 15000
                around = f"(around:{radius},{latitude},{longitude})"
                overpass_query = f"""
                    [out:json][timeout:20];
                    (
                      nwr["tourism"~"^(attraction|museum|viewpoint|gallery|zoo|theme_park)$"]["name"]{around};
                      nwr["historic"~"^(monument|castle|fort|memorial|ruins)$"]["name"]{around};
                      nwr["natural"="beach"]["name"]{around};
                    );
                    out center 80;
                """
                for i, overpass_url in enumerate(self.OVERPASS_URLS):
                    resp = await client.post(overpass_url, data={"data": overpass_query})
                    if resp.status_code < 500 or i == len(self.OVERPASS_URLS) - 1:
                        break
                self._check(resp)
                elements = resp.json().get("elements", [])
        except httpx.TimeoutException:
            raise PlacesProviderTimeout() from None
        except (httpx.HTTPError, ValueError, KeyError):
            raise PlacesProviderError() from None

        places, seen = [], set()
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name:en") or tags.get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            category = tags.get("tourism") or tags.get("historic") or tags.get("natural") or "place"
            address = ", ".join(
                filter(None, [tags.get("addr:street"), tags.get("addr:suburb"), tags.get("addr:city")])
            ) or None
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            # Places with Wikipedia/Wikidata entries are a reasonable proxy for "popular".
            popularity = int("wikipedia" in tags) + int("wikidata" in tags)
            places.append(
                (
                    -popularity,
                    name.lower(),
                    _place(
                        f"osm:{el['type']}/{el['id']}",
                        name,
                        category.replace("_", " ").capitalize(),
                        address,
                        None,
                        lat,
                        lon,
                        f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
                    ),
                )
            )
        places.sort(key=lambda p: (p[0], p[1]))
        return [p[2] for p in places[:limit]]


@lru_cache
def get_places_provider() -> PlacesProvider:
    settings = get_settings()
    if settings.places_provider.lower() == "osm":
        return OpenStreetMapPlacesProvider(settings.places_timeout_seconds, settings.places_user_agent)
    return MockPlacesProvider()
