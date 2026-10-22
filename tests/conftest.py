import os
import tempfile

# Point the app at a throwaway database and the mock places provider before it is imported.
_TMP_DIR = tempfile.mkdtemp(prefix="tripzy-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["APP_ENV"] = "test"
os.environ["PLACES_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services.auth import reset_login_limits  # noqa: E402

PASSWORD = "Passw0rd!"


@pytest.fixture
def app():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    reset_login_limits()
    fastapi_app.dependency_overrides.clear()
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def db(app):
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def anon(app):
    return TestClient(app)


@pytest.fixture
def make_user(app):
    """Create a user and return a TestClient signed in as them (with CSRF header set)."""

    def _make(name: str, email: str | None = None, password: str = PASSWORD) -> TestClient:
        client = TestClient(app)
        email = email or f"{name.lower()}@example.com"
        response = client.post("/api/auth/signup", json={"display_name": name, "email": email, "password": password})
        assert response.status_code == 201, response.text
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        client.user = response.json()["user"]
        return client

    return _make


@pytest.fixture
def alex(make_user):
    return make_user("Alex")


@pytest.fixture
def blair(make_user):
    return make_user("Blair")


@pytest.fixture
def casey(make_user):
    return make_user("Casey")


def befriend(a: TestClient, b: TestClient) -> None:
    r = a.post("/api/friend-requests", json={"recipient_id": b.user["id"]})
    assert r.status_code == 201, r.text
    r = b.post(f"/api/friend-requests/{r.json()['id']}/accept")
    assert r.status_code == 200, r.text


def create_trip(owner: TestClient, *members: TestClient, **fields) -> dict:
    body = {"name": "Goa Weekend", "destination": "North Goa, India", **fields}
    r = owner.post("/api/trips", json=body)
    assert r.status_code == 201, r.text
    trip = r.json()
    for m in members:
        r = owner.post(f"/api/trips/{trip['id']}/members", json={"user_id": m.user["id"]})
        assert r.status_code == 201, r.text
    return owner.get(f"/api/trips/{trip['id']}").json()


@pytest.fixture
def trip3(alex, blair, casey):
    """A trip owned by Alex with Blair and Casey as members."""
    return create_trip(alex, blair, casey)


def ids(*clients: TestClient) -> list[int]:
    return [c.user["id"] for c in clients]
