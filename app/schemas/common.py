from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


def text(max_length: int, min_length: int = 1):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)]


def optional_text(max_length: int):
    return Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=max_length)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
