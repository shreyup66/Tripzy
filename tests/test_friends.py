from app.models import Friendship
from tests.conftest import befriend


def test_search_users(alex, blair, casey):
    r = alex.get("/api/users/search", params={"q": "bla"})
    assert [u["display_name"] for u in r.json()] == ["Blair"]
    r = alex.get("/api/users/search", params={"q": "example.com"})
    assert {u["display_name"] for u in r.json()} == {"Blair", "Casey"}  # excludes self
    assert alex.get("/api/users/search", params={"q": "%%"}).json() == []  # wildcards are literal


def test_send_and_accept_request(alex, blair):
    r = alex.post("/api/friend-requests", json={"recipient_id": blair.user["id"]})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert [x["id"] for x in blair.get("/api/friend-requests?direction=incoming").json()] == [r.json()["id"]]
    assert [x["id"] for x in alex.get("/api/friend-requests?direction=outgoing").json()] == [r.json()["id"]]
    assert alex.post(f"/api/friend-requests/{r.json()['id']}/accept").status_code == 403  # requester can't accept
    assert blair.post(f"/api/friend-requests/{r.json()['id']}/accept").json()["status"] == "accepted"
    assert [f["id"] for f in alex.get("/api/friends").json()] == [blair.user["id"]]
    assert [f["id"] for f in blair.get("/api/friends").json()] == [alex.user["id"]]
    assert alex.get("/api/users/search", params={"q": "blair"}).json()[0]["relationship"] == "friend"


def test_reject_request(alex, blair):
    rid = alex.post("/api/friend-requests", json={"recipient_id": blair.user["id"]}).json()["id"]
    assert blair.post(f"/api/friend-requests/{rid}/reject").json()["status"] == "rejected"
    assert blair.post(f"/api/friend-requests/{rid}/accept").status_code == 400
    assert alex.get("/api/friends").json() == []
    # A new request after rejection reuses the same relationship row.
    r = alex.post("/api/friend-requests", json={"recipient_id": blair.user["id"]})
    assert r.status_code == 201 and r.json()["id"] == rid and r.json()["status"] == "pending"


def test_cancel_outgoing_request(alex, blair, casey):
    rid = alex.post("/api/friend-requests", json={"recipient_id": blair.user["id"]}).json()["id"]
    assert blair.delete(f"/api/friend-requests/{rid}").status_code == 403
    assert casey.delete(f"/api/friend-requests/{rid}").status_code == 404
    assert alex.delete(f"/api/friend-requests/{rid}").status_code == 204
    assert blair.get("/api/friend-requests?direction=incoming").json() == []


def test_self_friend_request_rejected(alex):
    r = alex.post("/api/friend-requests", json={"recipient_id": alex.user["id"]})
    assert r.status_code == 400 and r.json()["code"] == "SELF_FRIEND_REQUEST"


def test_duplicate_request_creates_no_duplicate(alex, blair, db):
    alex.post("/api/friend-requests", json={"recipient_id": blair.user["id"]})
    r = alex.post("/api/friend-requests", json={"recipient_id": blair.user["id"]})
    assert r.status_code == 409 and r.json()["code"] == "DUPLICATE_REQUEST"
    assert db.query(Friendship).count() == 1


def test_opposing_request_becomes_friendship(alex, blair, db):
    alex.post("/api/friend-requests", json={"recipient_id": blair.user["id"]})
    r = blair.post("/api/friend-requests", json={"recipient_id": alex.user["id"]})
    assert r.status_code == 201 and r.json()["status"] == "accepted"
    assert db.query(Friendship).count() == 1
    assert blair.post("/api/friend-requests", json={"recipient_id": alex.user["id"]}).status_code == 409


def test_request_to_unknown_user(alex):
    assert alex.post("/api/friend-requests", json={"recipient_id": 9999}).status_code == 404


def test_unfriend_also_removes_from_groups(alex, blair):
    befriend(alex, blair)
    gid = alex.post("/api/friend-groups", json={"name": "Trek"}).json()["id"]
    alex.post(f"/api/friend-groups/{gid}/members", json={"user_id": blair.user["id"]})
    assert blair.delete(f"/api/friends/{alex.user['id']}").status_code == 204
    assert alex.get("/api/friends").json() == []
    assert alex.get(f"/api/friend-groups/{gid}").json()["members"] == []
    assert alex.delete(f"/api/friends/{blair.user['id']}").status_code == 404
    # They can become friends again afterwards.
    befriend(alex, blair)
