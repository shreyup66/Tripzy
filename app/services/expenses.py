from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, not_found
from app.models import Expense, ExpenseShare, Trip, User
from app.schemas.expenses import ExpenseIn
from app.services.money import InvalidAmount, format_minor, parse_amount, split_equal

SUPPORTED_CURRENCIES = {"INR"}


def _invalid_amount() -> AppError:
    return AppError(422, "Enter a valid amount", "INVALID_EXPENSE_AMOUNT", "amount")


def _rounding_note(expense: Expense) -> str | None:
    if expense.split_method != "equal" or not expense.shares:
        return None
    if expense.total_minor % len(expense.shares) == 0:
        return None
    return (
        f"₹{format_minor(expense.total_minor)} can't be split evenly between {len(expense.shares)} people, "
        "so some shares are ₹0.01 higher."
    )


def serialize_expense(expense: Expense) -> dict:
    shares = sorted(expense.shares, key=lambda s: s.user_id)
    return {
        "id": expense.id,
        "trip_id": expense.trip_id,
        "description": expense.description,
        "amount": format_minor(expense.total_minor),
        "total_minor": expense.total_minor,
        "currency": expense.currency,
        "split_method": expense.split_method,
        "payer": expense.payer.public(),
        "created_by": expense.created_by,
        "created_at": expense.created_at.isoformat(),
        "shares": [
            {
                "user_id": s.user_id,
                "display_name": s.user.display_name,
                "share_minor": s.share_minor,
                "amount": format_minor(s.share_minor),
            }
            for s in shares
        ],
        "rounding_note": _rounding_note(expense),
    }


def list_expenses(db: Session, trip: Trip) -> list[Expense]:
    return list(
        db.scalars(
            select(Expense).where(Expense.trip_id == trip.id).order_by(Expense.created_at.desc(), Expense.id.desc())
        )
    )


def get_expense(db: Session, trip: Trip, expense_id: int) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None or expense.trip_id != trip.id:
        raise not_found("Expense")
    return expense


def _calculate_shares(data: ExpenseIn, total_minor: int, member_ids: set[int]) -> dict[int, int]:
    if data.split_method == "equal":
        ids = data.participant_ids or []
        if not ids:
            raise AppError(422, "Select at least one participant", "NO_PARTICIPANTS", "participant_ids")
        if len(set(ids)) != len(ids):
            raise AppError(422, "Each participant can be selected only once", "DUPLICATE_PARTICIPANT", "participant_ids")
        if not set(ids) <= member_ids:
            raise AppError(422, "All participants must be members of this trip", "PARTICIPANT_NOT_MEMBER", "participant_ids")
        return split_equal(total_minor, ids)

    if data.split_method == "custom":
        shares_in = data.shares or []
        if not shares_in:
            raise AppError(422, "Add a share for at least one participant", "NO_PARTICIPANTS", "shares")
        shares: dict[int, int] = {}
        for item in shares_in:
            if item.user_id in shares:
                raise AppError(422, "Each participant can have only one share", "DUPLICATE_PARTICIPANT", "shares")
            if item.user_id not in member_ids:
                raise AppError(422, "All participants must be members of this trip", "PARTICIPANT_NOT_MEMBER", "shares")
            try:
                shares[item.user_id] = parse_amount(item.amount, allow_zero=True)
            except InvalidAmount:
                raise AppError(422, "Enter a valid amount for each share", "INVALID_SHARE_AMOUNT", "shares") from None
        allocated = sum(shares.values())
        if allocated != total_minor:
            raise AppError(
                422,
                f"Shares add up to ₹{format_minor(allocated)} but the expense total is ₹{format_minor(total_minor)}",
                "SHARE_TOTAL_MISMATCH",
                "shares",
            )
        return shares

    raise AppError(422, "Split method must be 'equal' or 'custom'", "INVALID_SPLIT_METHOD", "split_method")


def create_expense(db: Session, trip: Trip, user: User, data: ExpenseIn) -> Expense:
    try:
        total_minor = parse_amount(data.amount)
    except InvalidAmount:
        raise _invalid_amount() from None
    currency = (data.currency or "INR").upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise AppError(422, "Only INR is supported at the moment", "UNSUPPORTED_CURRENCY", "currency")
    member_ids = trip.member_ids()
    if data.payer_id not in member_ids:
        raise AppError(422, "The payer must be a member of this trip", "PAYER_NOT_MEMBER", "payer_id")
    shares = _calculate_shares(data, total_minor, member_ids)
    assert sum(shares.values()) == total_minor

    # Expense and shares are written together; any failure rolls back both.
    try:
        expense = Expense(
            trip_id=trip.id,
            payer_id=data.payer_id,
            description=data.description,
            total_minor=total_minor,
            currency=currency,
            split_method=data.split_method,
            created_by=user.id,
        )
        expense.shares = [ExpenseShare(user_id=uid, share_minor=amt) for uid, amt in shares.items()]
        db.add(expense)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(expense)
    return expense


def delete_expense(db: Session, trip: Trip, expense_id: int) -> None:
    db.delete(get_expense(db, trip, expense_id))
    db.commit()


def compute_balances(db: Session, trip: Trip) -> dict:
    """net = paid - owed. Positive: should receive money. Net positions always sum to zero."""
    users: dict[int, User] = {m.user_id: m.user for m in trip.members}
    paid: dict[int, int] = dict.fromkeys(users, 0)
    owed: dict[int, int] = dict.fromkeys(users, 0)
    for expense in list_expenses(db, trip):
        users.setdefault(expense.payer_id, expense.payer)
        paid[expense.payer_id] = paid.get(expense.payer_id, 0) + expense.total_minor
        for share in expense.shares:
            users.setdefault(share.user_id, share.user)
            owed[share.user_id] = owed.get(share.user_id, 0) + share.share_minor

    balances = []
    for uid, u in sorted(users.items(), key=lambda kv: (kv[1].display_name.lower(), kv[0])):
        p, o = paid.get(uid, 0), owed.get(uid, 0)
        balances.append(
            {
                "user_id": uid,
                "display_name": u.display_name,
                "paid_minor": p,
                "owed_minor": o,
                "net_minor": p - o,
                "paid": format_minor(p),
                "owed": format_minor(o),
                "net": format_minor(p - o),
            }
        )
    assert sum(b["net_minor"] for b in balances) == 0
    return {"currency": "INR", "balances": balances, "settlements": suggest_settlements(balances)}


def suggest_settlements(balances: list[dict]) -> list[dict]:
    """Greedy match of largest debtor to largest creditor."""
    creditors = sorted(([b["net_minor"], b] for b in balances if b["net_minor"] > 0), key=lambda x: (-x[0], x[1]["user_id"]))
    debtors = sorted(([-b["net_minor"], b] for b in balances if b["net_minor"] < 0), key=lambda x: (-x[0], x[1]["user_id"]))
    result, i, j = [], 0, 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][0], creditors[j][0])
        d, c = debtors[i][1], creditors[j][1]
        result.append(
            {
                "from_user_id": d["user_id"],
                "from_name": d["display_name"],
                "to_user_id": c["user_id"],
                "to_name": c["display_name"],
                "amount_minor": amount,
                "amount": format_minor(amount),
            }
        )
        debtors[i][0] -= amount
        creditors[j][0] -= amount
        if debtors[i][0] == 0:
            i += 1
        if creditors[j][0] == 0:
            j += 1
    return result
