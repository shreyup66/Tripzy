from tests.conftest import befriend


def test_create_multiple_groups_and_rename(alex):
    a = alex.post("/api/friend-groups", json={"name": "College"}).json()
    alex.post("/api/friend-groups", json={"name": "Family"})
    assert sorted(g["name"] for g in alex.get("/api/friend-groups").json()) == ["College", "Family"]
    r = alex.patch(f"/api/friend-groups/{a['id']}", json={"name": "  Uni friends "})
    assert r.json()["name"] == "Uni friends"
    assert alex.post("/api/friend-groups", json={"name": ""}).status_code == 422


def test_add_and_remove_friend(alex, blair):
    befriend(alex, blair)
    gid = alex.post("/api/friend-groups", json={"name": "Trek"}).json()["id"]
    r = alex.post(f"/api/friend-groups/{gid}/members", json={"user_id": blair.user["id"]})
    assert r.status_code == 201 and [m["id"] for m in r.json()["members"]] == [blair.user["id"]]
    assert alex.delete(f"/api/friend-groups/{gid}/members/{blair.user['id']}").status_code == 204
    assert alex.get(f"/api/friend-groups/{gid}").json()["members"] == []
    assert [f["id"] for f in alex.get("/api/friends").json()] == [blair.user["id"]]  # still friends


def test_add_same_friend_twice_prevented(alex, blair):
    befriend(alex, blair)
    gid = alex.post("/api/friend-groups", json={"name": "Trek"}).json()["id"]
    alex.post(f"/api/friend-groups/{gid}/members", json={"user_id": blair.user["id"]})
    r = alex.post(f"/api/friend-groups/{gid}/members", json={"user_id": blair.user["id"]})
    assert r.status_code == 409
    assert len(alex.get(f"/api/friend-groups/{gid}").json()["members"]) == 1


def test_add_non_friend_rejected(alex, blair):
    gid = alex.post("/api/friend-groups", json={"name": "Trek"}).json()["id"]
    r = alex.post(f"/api/friend-groups/{gid}/members", json={"user_id": blair.user["id"]})
    assert r.status_code == 422 and r.json()["code"] == "NOT_A_FRIEND"


def test_delete_group_keeps_users_and_friendships(alex, blair):
    befriend(alex, blair)
    gid = alex.post("/api/friend-groups", json={"name": "Trek"}).json()["id"]
    alex.post(f"/api/friend-groups/{gid}/members", json={"user_id": blair.user["id"]})
    assert alex.delete(f"/api/friend-groups/{gid}").status_code == 204
    assert alex.get(f"/api/friend-groups/{gid}").status_code == 404
    assert len(alex.get("/api/friends").json()) == 1
    assert blair.get("/api/account").status_code == 200


def test_groups_are_private_to_owner(alex, blair):
    gid = alex.post("/api/friend-groups", json={"name": "Trek"}).json()["id"]
    assert blair.get(f"/api/friend-groups/{gid}").status_code == 404
    assert blair.patch(f"/api/friend-groups/{gid}", json={"name": "Mine"}).status_code == 404
    assert blair.delete(f"/api/friend-groups/{gid}").status_code == 404
    assert blair.get("/api/friend-groups").json() == []
