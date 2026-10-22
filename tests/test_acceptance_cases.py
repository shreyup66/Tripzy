"""Acceptance tests mapped 1:1 to the PBL Assignment 7 spreadsheet (spec §11.3).

LS-03 and LS-04 need a real browser and live in tests/e2e/test_geolocation.py.
"""

from app.models import Expense, ExpenseShare, SavedLocation, Trip, TripMember
from tests.conftest import create_trip, ids


def add_expense(client, trip, **body):
    payload = {"description": "Dinner", "amount": "900.00", "currency": "INR", "payer_id": client.user["id"], "split_method": "equal"}
    payload.update(body)
    return client.post(f"/api/trips/{trip['id']}/expenses", json=payload)


def nets(client, trip):
    return {b["user_id"]: b["net_minor"] for b in client.get(f"/api/trips/{trip['id']}/balances").json()["balances"]}


# ---------------- Budget Splitter ----------------


def test_add_expense_valid(alex, blair, casey, trip3):
    """BS-01: Add expense with valid amount, payer and participant -> expense is added."""
    r = add_expense(alex, trip3, payer_id=blair.user["id"], participant_ids=ids(alex, blair))
    assert r.status_code == 201
    expense = r.json()
    assert expense["total_minor"] == 90000 and expense["payer"]["id"] == blair.user["id"]
    assert sum(s["share_minor"] for s in expense["shares"]) == expense["total_minor"]
    assert [e["id"] for e in alex.get(f"/api/trips/{trip3['id']}/expenses").json()] == [expense["id"]]


def test_negative_expense_rejected(alex, blair, trip3, db):
    """BS-02: Negative amount -> error "Enter a valid amount"."""
    before = db.query(Expense).count()
    r = add_expense(alex, trip3, amount="-250.00", participant_ids=ids(alex, blair))
    assert r.status_code in (400, 422)
    assert "valid amount" in r.text.lower()
    assert r.json()["detail"] == "Enter a valid amount"
    assert db.query(Expense).count() == before


def test_equal_split_all_members(alex, blair, casey, trip3):
    """BS-03: Select all trip members, equal split -> split among all selected members."""
    all_ids = [m["id"] for m in trip3["members"]]
    r = add_expense(alex, trip3, amount="900.00", participant_ids=all_ids)
    shares = {s["user_id"]: s["share_minor"] for s in r.json()["shares"]}
    assert shares == {uid: 30000 for uid in all_ids}


def test_split_selected_members_only(alex, blair, casey, trip3):
    """BS-04: Only selected participants receive shares."""
    r = add_expense(alex, trip3, amount="600.00", participant_ids=ids(alex, blair))
    shares = {s["user_id"]: s["share_minor"] for s in r.json()["shares"]}
    assert shares == {alex.user["id"]: 30000, blair.user["id"]: 30000}
    assert casey.user["id"] not in shares
    assert nets(alex, trip3)[casey.user["id"]] == 0


def test_custom_split_reconciles_total(alex, blair, casey, trip3):
    """BS-05: Custom shares that add up to the total -> expense added, amounts correct."""
    r = add_expense(alex, trip3, description="Cab", amount="500.00", split_method="custom", shares=[
        {"user_id": alex.user["id"], "amount": "100.00"},
        {"user_id": blair.user["id"], "amount": "250.00"},
        {"user_id": casey.user["id"], "amount": "150.00"},
    ])
    assert r.status_code == 201
    shares = {s["user_id"]: s["share_minor"] for s in r.json()["shares"]}
    assert shares == {alex.user["id"]: 10000, blair.user["id"]: 25000, casey.user["id"]: 15000}
    assert nets(alex, trip3) == {alex.user["id"]: 40000, blair.user["id"]: -25000, casey.user["id"]: -15000}


def test_delete_expense_updates_balances(alex, blair, casey, trip3, db):
    """BS-06: Delete an expense -> expense deleted and balances update."""
    keep = add_expense(alex, trip3, amount="300.00", participant_ids=ids(alex, blair, casey)).json()
    gone = add_expense(blair, trip3, amount="900.00", payer_id=blair.user["id"], participant_ids=ids(alex, blair, casey)).json()
    assert nets(alex, trip3)[blair.user["id"]] == -10000 + 60000
    r = alex.delete(f"/api/trips/{trip3['id']}/expenses/{gone['id']}")
    assert r.status_code == 204
    assert db.get(Expense, gone["id"]) is None
    assert db.query(ExpenseShare).filter_by(expense_id=gone["id"]).count() == 0
    assert [e["id"] for e in alex.get(f"/api/trips/{trip3['id']}/expenses").json()] == [keep["id"]]
    assert nets(alex, trip3) == {alex.user["id"]: 20000, blair.user["id"]: -10000, casey.user["id"]: -10000}


# ---------------- Trip Management ----------------


def test_create_trip(alex):
    """TM-01: Create trip with name, destination, details and dates -> trip created."""
    r = alex.post("/api/trips", json={"name": "Goa Weekend", "destination": "North Goa, India",
                                      "description": "A weekend with friends", "start_date": "2026-12-11", "end_date": "2026-12-14"})
    assert r.status_code == 201
    trip = r.json()
    assert (trip["name"], trip["destination"], trip["start_date"], trip["end_date"]) == (
        "Goa Weekend", "North Goa, India", "2026-12-11", "2026-12-14")
    assert trip["id"] in [t["id"] for t in alex.get("/api/trips").json()]


def test_owner_adds_trip_member(alex, blair):
    """TM-02: Owner adds a selected user -> member is added."""
    trip = create_trip(alex)
    r = alex.post(f"/api/trips/{trip['id']}/members", json={"user_id": blair.user["id"]})
    assert r.status_code == 201 and r.json()["role"] == "member"
    assert blair.user["id"] in [m["id"] for m in alex.get(f"/api/trips/{trip['id']}/members").json()]
    assert blair.get(f"/api/trips/{trip['id']}").status_code == 200


def test_owner_removes_trip_member(alex, blair, casey):
    """TM-03: Owner removes a selected member -> member is removed."""
    trip = create_trip(alex, blair, casey)
    assert alex.delete(f"/api/trips/{trip['id']}/members/{blair.user['id']}").status_code == 204
    members = [m["id"] for m in alex.get(f"/api/trips/{trip['id']}/members").json()]
    assert blair.user["id"] not in members and casey.user["id"] in members


def test_delete_trip_cascades_data(alex, blair, trip3, db):
    """TM-04: Delete trip -> trip and dependent data are deleted."""
    tid = trip3["id"]
    add_expense(alex, trip3, participant_ids=ids(alex, blair))
    alex.post(f"/api/trips/{tid}/locations", json={"name": "Baga Beach", "provider_place_id": "mock-goa-1"})
    other = create_trip(alex, blair)
    add_expense(alex, other, participant_ids=ids(alex, blair))

    assert alex.delete(f"/api/trips/{tid}").status_code == 204
    assert alex.get(f"/api/trips/{tid}").status_code == 404
    assert db.get(Trip, tid) is None
    assert db.query(TripMember).filter_by(trip_id=tid).count() == 0
    assert db.query(Expense).filter_by(trip_id=tid).count() == 0
    assert db.query(SavedLocation).filter_by(trip_id=tid).count() == 0
    # Only the other trip's single expense and its two shares remain.
    assert db.query(Expense).count() == 1 and db.query(ExpenseShare).count() == 2


# ---------------- Location Suggestion ----------------


def test_save_location_to_trip(alex, blair):
    """LS-01: Search/select a place and save -> location is saved to the trip."""
    trip = create_trip(alex, blair)
    place = alex.get(f"/api/trips/{trip['id']}/locations/suggestions", params={"query": "Goa"}).json()["results"][1]
    body = {k: place[k] for k in ("provider_place_id", "name", "category", "address", "provider_url")}
    r = alex.post(f"/api/trips/{trip['id']}/locations", json=body)
    assert r.status_code == 201
    saved = blair.get(f"/api/trips/{trip['id']}/locations").json()
    assert [(s["name"], s["provider_place_id"]) for s in saved] == [(place["name"], place["provider_place_id"])]


def test_popular_location_suggestions(alex):
    """LS-02: Open Location Suggestions -> popular places are shown."""
    trip = create_trip(alex)
    r = alex.get(f"/api/trips/{trip['id']}/locations/suggestions")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) >= 3
    assert all(p["name"] and p["category"] for p in results)
    assert alex.get(f"/trips/{trip['id']}/locations").status_code == 200
