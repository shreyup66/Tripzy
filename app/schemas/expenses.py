from typing import Any

from pydantic import Field

from app.schemas.common import Strict, text


class ShareIn(Strict):
    user_id: int
    # Parsed by the server into integer paise; kept loose so bad input yields "Enter a valid amount".
    amount: Any = None


class ExpenseIn(Strict):
    description: text(200)
    amount: Any = None
    currency: str = "INR"
    payer_id: int
    split_method: str = "equal"
    participant_ids: list[int] | None = Field(default=None, max_length=100)
    shares: list[ShareIn] | None = Field(default=None, max_length=100)
