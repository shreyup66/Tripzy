"""Money helpers. All amounts are integer minor units (paise for INR)."""

import re
from decimal import Decimal

MAX_AMOUNT_MINOR = 10_000_000_00  # ₹1,00,00,000 per expense
_AMOUNT_RE = re.compile(r"-?(?:\d+(?:\.\d{0,2})?|\.\d{1,2})")


class InvalidAmount(ValueError):
    pass


def parse_amount(value, *, allow_zero: bool = False) -> int:
    """Parse "125.50" / 125.5 / 125 into 12550. Rejects negatives, >2 decimals and junk."""
    if value is None or isinstance(value, bool):
        raise InvalidAmount("missing")
    text = str(value).strip() if isinstance(value, (str, int, float)) else None
    if not text or not _AMOUNT_RE.fullmatch(text):
        raise InvalidAmount("malformed")
    minor = int(Decimal(text) * 100)
    if minor < 0 or (minor == 0 and not allow_zero) or minor > MAX_AMOUNT_MINOR:
        raise InvalidAmount("out of range")
    return minor


def format_minor(minor: int) -> str:
    sign = "-" if minor < 0 else ""
    whole, frac = divmod(abs(minor), 100)
    return f"{sign}{whole}.{frac:02d}"


def split_equal(total_minor: int, user_ids: list[int]) -> dict[int, int]:
    """First `remainder` users (by ascending ID) get one extra paisa, so shares sum to the total."""
    ordered = sorted(user_ids)
    base, remainder = divmod(total_minor, len(ordered))
    return {uid: base + (1 if i < remainder else 0) for i, uid in enumerate(ordered)}
