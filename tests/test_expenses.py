import pytest

from app.models import Expense, ExpenseShare
from app.services.expenses import suggest_settlements
from app.services.money import InvalidAmount, format_minor, parse_amount, split_equal
from tests.conftest import create_trip, ids

# ---------- unit tests ----------


@pytest.mark.parametrize(
    ("text", "minor"),
    [("125.50", 12550), ("125.5", 12550), ("900", 90000), (900, 90000), (12.25, 1225), (" 1.05 ", 105), (".5", 50)],
)
def test_parse_amount_valid(text, minor):
    assert parse_amount(text) == minor


@pytest.mark.parametrize("text", [None, "", "abc", "-1", "-0.01", "0", "0.00", "1.234", "1e3", "NaN", "100000000.01", True, [], "₹10"])
def test_parse_amount_invalid(text):
    with pytest.raises(InvalidAmount):
        parse_amount(text)


def test_parse_amount_allow_zero_for_shares():
    assert parse_amount("0", allow_zero=True) == 0


def test_format_minor():
    assert format_minor(12550) == "125.50" and format_minor(5) == "0.05" and format_minor(-30000) == "-300.00"


def test_split_equal_remainder_goes_to_lowest_ids():
    shares = split_equal(10000, [3, 1, 2])  # ₹100 between 3 people
    assert shares == {1: 3334, 2: 3333, 3: 3333}
    assert sum(shares.values()) == 10000


@pytest.mark.parametrize("total", [1, 2, 99, 100, 101, 12345, 99999])
@pytest.mark.parametrize("n", [1, 2, 3, 7])
def test_split_equal_always_sums_exactly(total, n):
    shares = split_equal(total, list(range(1, n + 1)))
    assert sum(shares.values()) == total
    assert max(shares.values()) - min(shares.values()) <= 1


def test_settlements_match_debtors_to_creditors():
    balances = [
        {"user_id": 1, "display_name": "A", "net_minor": 600},
        {"user_id": 2, "display_name": "B", "net_minor": -300},
        {"user_id": 3, "display_name": "C", "net_minor": -300},
    ]
    result = suggest_settlements(balances)
    assert [(s["from_user_id"], s["to_user_id"], s["amount_minor"]) for s in result] == [(2, 1, 300), (3, 1, 300)]


# ---------- API tests ----------


def post_expense(client, trip, **body):
    payload = {"description": "Dinner", "amount": "900.00", "currency": "INR", "payer_id": client.user["id"], "split_method": "equal"}
    payload.update(body)
    return client.post(f"/api/trips/{trip['id']}/expenses", json=payload)


def balances_by_name(client, trip):
    return {b["display_name"]: b["net_minor"] for b in client.get(f"/api/trips/{trip['id']}/balances").json()["balances"]}


def test_spec_example_alex_pays_900(alex, blair, casey, trip3):
    r = post_expense(alex, trip3, participant_ids=ids(alex, blair, casey))
    assert r.status_code == 201
    assert [s["share_minor"] for s in r.json()["shares"]] == [30000, 30000, 30000]
    assert balances_by_name(alex, trip3) == {"Alex": 60000, "Blair": -30000, "Casey": -30000}


@pytest.mark.parametrize("amount", ["0", "0.00", "abc", "", None, "12.345", "1000000000", -5, "-0.5"])
def test_invalid_amounts_rejected(alex, blair, trip3, db, amount):
    r = post_expense(alex, trip3, amount=amount, participant_ids=ids(alex, blair))
    assert r.status_code == 422
    assert r.json()["detail"] == "Enter a valid amount"
    assert db.query(Expense).count() == 0


def test_missing_amount_field(alex, blair, trip3):
    r = alex.post(f"/api/trips/{trip3['id']}/expenses", json={"description": "X", "payer_id": alex.user["id"], "participant_ids": ids(alex)})
    assert r.status_code == 422 and "valid amount" in r.text.lower()


def test_payer_must_be_member(alex, blair, make_user, trip3):
    outsider = make_user("Dev")
    r = post_expense(alex, trip3, payer_id=outsider.user["id"], participant_ids=ids(alex))
    assert r.status_code == 422 and r.json()["code"] == "PAYER_NOT_MEMBER"


def test_participants_must_be_members(alex, make_user, trip3):
    outsider = make_user("Dev")
    r = post_expense(alex, trip3, participant_ids=[alex.user["id"], outsider.user["id"]])
    assert r.status_code == 422 and r.json()["code"] == "PARTICIPANT_NOT_MEMBER"
    r = post_expense(alex, trip3, split_method="custom", shares=[{"user_id": outsider.user["id"], "amount": "900"}])
    assert r.status_code == 422 and r.json()["code"] == "PARTICIPANT_NOT_MEMBER"


def test_needs_at_least_one_participant(alex, trip3):
    assert post_expense(alex, trip3, participant_ids=[]).json()["code"] == "NO_PARTICIPANTS"
    assert post_expense(alex, trip3, split_method="custom", shares=[]).json()["code"] == "NO_PARTICIPANTS"


def test_duplicate_participants_rejected(alex, trip3):
    assert post_expense(alex, trip3, participant_ids=ids(alex, alex)).status_code == 422


def test_invalid_split_method(alex, trip3):
    r = post_expense(alex, trip3, split_method="weird", participant_ids=ids(alex))
    assert r.json()["code"] == "INVALID_SPLIT_METHOD"


def test_unsupported_currency(alex, trip3):
    assert post_expense(alex, trip3, currency="USD", participant_ids=ids(alex)).json()["code"] == "UNSUPPORTED_CURRENCY"


def test_custom_shares_must_sum_to_total_no_partial_write(alex, blair, casey, trip3, db):
    r = post_expense(alex, trip3, amount="500.00", split_method="custom", shares=[
        {"user_id": alex.user["id"], "amount": "100.00"},
        {"user_id": blair.user["id"], "amount": "250.00"},
        {"user_id": casey.user["id"], "amount": "100.00"},
    ])
    assert r.status_code == 422 and r.json()["code"] == "SHARE_TOTAL_MISMATCH"
    assert db.query(Expense).count() == 0 and db.query(ExpenseShare).count() == 0


def test_custom_share_amounts_validated(alex, blair, trip3):
    r = post_expense(alex, trip3, amount="100", split_method="custom", shares=[
        {"user_id": alex.user["id"], "amount": "150"}, {"user_id": blair.user["id"], "amount": "-50"}])
    assert r.json()["code"] == "INVALID_SHARE_AMOUNT"


def test_custom_share_can_be_zero(alex, blair, trip3):
    r = post_expense(alex, trip3, amount="100", split_method="custom", shares=[
        {"user_id": alex.user["id"], "amount": "0"}, {"user_id": blair.user["id"], "amount": "100"}])
    assert r.status_code == 201


def test_equal_split_with_remainder_paise(alex, blair, casey, trip3):
    r = post_expense(alex, trip3, amount="100.00", participant_ids=ids(casey, blair, alex))
    body = r.json()
    assert sum(s["share_minor"] for s in body["shares"]) == 10000
    assert sorted(s["share_minor"] for s in body["shares"]) == [3333, 3333, 3334]
    assert body["rounding_note"]


def test_net_balances_always_sum_to_zero(alex, blair, casey, trip3):
    post_expense(alex, trip3, amount="100.00", participant_ids=ids(alex, blair, casey))
    post_expense(blair, trip3, amount="333.33", payer_id=blair.user["id"], participant_ids=ids(blair, casey))
    post_expense(casey, trip3, amount="47.10", payer_id=alex.user["id"], split_method="custom",
                 shares=[{"user_id": casey.user["id"], "amount": "47.10"}])
    data = alex.get(f"/api/trips/{trip3['id']}/balances").json()
    assert sum(b["net_minor"] for b in data["balances"]) == 0
    settled = {b["user_id"]: b["net_minor"] for b in data["balances"]}
    for s in data["settlements"]:
        settled[s["from_user_id"]] += s["amount_minor"]
        settled[s["to_user_id"]] -= s["amount_minor"]
    assert set(settled.values()) == {0}


def test_view_single_expense(alex, blair, trip3):
    eid = post_expense(alex, trip3, participant_ids=ids(alex, blair)).json()["id"]
    r = blair.get(f"/api/trips/{trip3['id']}/expenses/{eid}")
    assert r.status_code == 200 and r.json()["payer"]["id"] == alex.user["id"]
    other = create_trip(alex)
    assert alex.get(f"/api/trips/{other['id']}/expenses/{eid}").status_code == 404


def test_non_member_cannot_read_or_add_expenses(alex, blair, make_user, trip3):
    post_expense(alex, trip3, participant_ids=ids(alex, blair))
    outsider = make_user("Dev")
    assert outsider.get(f"/api/trips/{trip3['id']}/expenses").status_code == 404
    assert outsider.get(f"/api/trips/{trip3['id']}/balances").status_code == 404
    assert post_expense(outsider, trip3, payer_id=alex.user["id"], participant_ids=ids(alex)).status_code == 404


def test_member_can_delete_expense(alex, blair, trip3):
    eid = post_expense(alex, trip3, participant_ids=ids(alex, blair)).json()["id"]
    assert blair.delete(f"/api/trips/{trip3['id']}/expenses/{eid}").status_code == 204
    assert blair.delete(f"/api/trips/{trip3['id']}/expenses/{eid}").status_code == 404
