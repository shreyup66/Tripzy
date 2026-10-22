from fastapi.testclient import TestClient

from app.models import User
from tests.conftest import PASSWORD


def signup(client, **overrides):
    body = {"display_name": "Alex", "email": "alex@example.com", "password": PASSWORD, **overrides}
    return client.post("/api/auth/signup", json=body)


def test_signup_creates_account_and_session(anon):
    r = signup(anon)
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "alex@example.com"
    assert anon.get("/api/account").json()["display_name"] == "Alex"


def test_duplicate_email_rejected_case_insensitively(anon, app):
    assert signup(anon).status_code == 201
    r = signup(TestClient(app), email="ALEX@Example.com")
    assert r.status_code == 409
    assert r.json()["code"] == "EMAIL_TAKEN"


def test_signup_validation(anon):
    assert signup(anon, display_name="   ").status_code == 422
    assert signup(anon, email="not-an-email").status_code == 422
    r = signup(anon, password="short")
    assert r.status_code == 422 and r.json()["code"] == "WEAK_PASSWORD"
    assert signup(anon, password="lettersonly").status_code == 422
    assert anon.post("/api/auth/signup", json={}).status_code == 422


def test_password_is_hashed(anon, db):
    signup(anon)
    user = db.query(User).one()
    assert PASSWORD not in user.password_hash
    assert user.password_hash.startswith("$argon2")


def test_login_logout(alex, app):
    client = TestClient(app)
    assert client.post("/api/auth/login", json={"email": "alex@example.com", "password": "wrong"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "ALEX@example.com", "password": PASSWORD})
    assert r.status_code == 200
    client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert client.get("/api/account").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/account").status_code == 401


def test_login_rate_limited(alex, app):
    client = TestClient(app)
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "alex@example.com", "password": "wrong"})
    r = client.post("/api/auth/login", json={"email": "alex@example.com", "password": PASSWORD})
    assert r.status_code == 429


def test_protected_routes_require_login(anon):
    r = anon.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert anon.get("/trips/1", follow_redirects=False).status_code == 303
    r = anon.get("/api/trips")
    assert r.status_code == 401 and r.json()["code"] == "NOT_AUTHENTICATED"
    assert anon.post("/api/trips", json={"name": "x", "destination": "y"}).status_code == 401


def test_mutations_require_csrf_token(alex):
    token = alex.headers.pop("X-CSRF-Token")
    r = alex.post("/api/trips", json={"name": "Trip", "destination": "Goa"})
    assert r.status_code == 403 and r.json()["code"] == "CSRF_FAILED"
    alex.headers["X-CSRF-Token"] = "wrong"
    assert alex.post("/api/trips", json={"name": "Trip", "destination": "Goa"}).status_code == 403
    alex.headers["X-CSRF-Token"] = token
    assert alex.post("/api/trips", json={"name": "Trip", "destination": "Goa"}).status_code == 201


def test_update_profile_keeps_email_unique(alex, blair):
    r = alex.patch("/api/account", json={"display_name": "Alex P", "email": "ALEXP@example.com"})
    assert r.status_code == 200
    assert r.json() == {**r.json(), "display_name": "Alex P", "email": "alexp@example.com"}
    r = alex.patch("/api/account", json={"email": "blair@example.com"})
    assert r.status_code == 409


def test_change_password(alex, app):
    r = alex.patch("/api/account", json={"current_password": "nope", "new_password": "NewPassw0rd"})
    assert r.status_code == 422 and r.json()["field"] == "current_password"
    assert alex.patch("/api/account", json={"current_password": PASSWORD, "new_password": "NewPassw0rd"}).status_code == 200
    client = TestClient(app)
    assert client.post("/api/auth/login", json={"email": "alex@example.com", "password": "NewPassw0rd"}).status_code == 200


def test_account_endpoint_has_no_user_id_to_tamper_with(alex, blair):
    # AUTH-06: the account API always resolves the signed-in user, never a URL ID.
    assert alex.get("/api/account").json()["id"] == alex.user["id"]
    assert blair.get("/api/account").json()["id"] == blair.user["id"]
