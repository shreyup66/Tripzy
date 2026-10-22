from tests.conftest import create_trip, ids


def test_create_trip_adds_owner_as_member(alex):
    r = alex.post("/api/trips", json={"name": " Goa Weekend ", "destination": "North Goa, India",
                                      "description": "A weekend with friends", "start_date": "2026-12-11", "end_date": "2026-12-14"})
    assert r.status_code == 201
    trip = r.json()
    assert trip["name"] == "Goa Weekend" and trip["is_owner"]
    assert [(m["id"], m["role"]) for m in trip["members"]] == [(alex.user["id"], "owner")]


def test_create_trip_requires_name_and_destination(alex):
    assert alex.post("/api/trips", json={"name": "", "destination": "Goa"}).status_code == 422
    assert alex.post("/api/trips", json={"name": "Trip"}).status_code == 422


def test_end_date_before_start_date_rejected(alex):
    r = alex.post("/api/trips", json={"name": "T", "destination": "Goa", "start_date": "2026-12-14", "end_date": "2026-12-11"})
    assert r.status_code == 422 and r.json()["field"] == "end_date"
    trip = create_trip(alex, start_date="2026-12-11")
    assert alex.patch(f"/api/trips/{trip['id']}", json={"end_date": "2026-12-01"}).status_code == 422


def test_list_trips_only_includes_own(alex, blair, casey):
    t1 = create_trip(alex, blair)
    create_trip(casey)
    assert [t["id"] for t in blair.get("/api/trips").json()] == [t1["id"]]
    assert len(alex.get("/api/trips").json()) == 1


def test_create_trip_with_preselected_members(alex, blair, casey):
    r = alex.post("/api/trips", json={"name": "T", "destination": "Goa", "member_ids": ids(blair, casey, alex)})
    assert r.status_code == 201
    assert sorted(m["id"] for m in r.json()["members"]) == sorted(ids(alex, blair, casey))
    assert alex.post("/api/trips", json={"name": "T", "destination": "Goa", "member_ids": [999]}).status_code == 422


def test_edit_trip(alex, blair):
    trip = create_trip(alex, blair)
    r = alex.patch(f"/api/trips/{trip['id']}", json={"name": "Goa Long Weekend", "description": None})
    assert r.status_code == 200 and r.json()["name"] == "Goa Long Weekend"
    assert blair.patch(f"/api/trips/{trip['id']}", json={"name": "Mine"}).status_code == 403


def test_non_member_cannot_view_trip(alex, casey):
    trip = create_trip(alex)
    assert casey.get(f"/api/trips/{trip['id']}").status_code == 404
    assert casey.get(f"/api/trips/{trip['id']}/members").status_code == 404
    assert casey.get(f"/trips/{trip['id']}").status_code == 404


def test_non_owner_cannot_delete_trip_or_manage_members(alex, blair, casey):
    trip = create_trip(alex, blair)
    assert blair.delete(f"/api/trips/{trip['id']}").status_code == 403
    assert blair.post(f"/api/trips/{trip['id']}/members", json={"user_id": casey.user["id"]}).status_code == 403
    assert blair.delete(f"/api/trips/{trip['id']}/members/{alex.user['id']}").status_code == 403
    assert alex.get(f"/api/trips/{trip['id']}").status_code == 200


def test_add_member_by_email_and_duplicate(alex, blair):
    trip = create_trip(alex)
    r = alex.post(f"/api/trips/{trip['id']}/members", json={"email": "BLAIR@example.com"})
    assert r.status_code == 201 and r.json()["id"] == blair.user["id"]
    r = alex.post(f"/api/trips/{trip['id']}/members", json={"user_id": blair.user["id"]})
    assert r.status_code == 409 and r.json()["code"] == "DUPLICATE_MEMBER"
    assert len(alex.get(f"/api/trips/{trip['id']}/members").json()) == 2


def test_add_nonexistent_member(alex):
    trip = create_trip(alex)
    assert alex.post(f"/api/trips/{trip['id']}/members", json={"user_id": 9999}).status_code == 404
    assert alex.post(f"/api/trips/{trip['id']}/members", json={"email": "nobody@example.com"}).status_code == 404
    assert alex.post(f"/api/trips/{trip['id']}/members", json={}).status_code == 422


def test_owner_cannot_remove_themselves(alex):
    trip = create_trip(alex)
    r = alex.delete(f"/api/trips/{trip['id']}/members/{alex.user['id']}")
    assert r.status_code == 400 and r.json()["code"] == "OWNER_CANNOT_LEAVE"


def test_member_with_expenses_cannot_be_removed(alex, blair):
    trip = create_trip(alex, blair)
    alex.post(f"/api/trips/{trip['id']}/expenses", json={"description": "Cab", "amount": "100", "payer_id": alex.user["id"],
                                                        "split_method": "equal", "participant_ids": ids(alex, blair)})
    r = alex.delete(f"/api/trips/{trip['id']}/members/{blair.user['id']}")
    assert r.status_code == 409 and r.json()["code"] == "MEMBER_HAS_EXPENSES"


def test_removed_member_loses_access(alex, blair):
    trip = create_trip(alex, blair)
    assert alex.delete(f"/api/trips/{trip['id']}/members/{blair.user['id']}").status_code == 204
    assert blair.get(f"/api/trips/{trip['id']}").status_code == 404
