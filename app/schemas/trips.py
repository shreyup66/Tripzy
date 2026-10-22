from datetime import date

from pydantic import Field

from app.schemas.common import Strict, optional_text, text


class TripCreateIn(Strict):
    name: text(120)
    destination: text(200)
    description: optional_text(2000) = None
    start_date: date | None = None
    end_date: date | None = None
    member_ids: list[int] = Field(default_factory=list, max_length=50)


class TripUpdateIn(Strict):
    name: text(120) | None = None
    destination: text(200) | None = None
    description: optional_text(2000) = None
    start_date: date | None = None
    end_date: date | None = None
