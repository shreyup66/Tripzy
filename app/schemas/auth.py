from pydantic import EmailStr, Field

from app.schemas.common import Strict, text


class SignupIn(Strict):
    display_name: text(80)
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AccountUpdateIn(Strict):
    display_name: text(80) | None = None
    email: EmailStr | None = None
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str | None = Field(default=None, max_length=128)
