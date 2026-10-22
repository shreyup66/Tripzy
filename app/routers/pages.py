from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_optional_user
from app.errors import AppError
from app.models import User
from app.security import ensure_csrf_token
from app.services.trips import get_trip_for_member

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def render(request: Request, name: str, user: User | None, status_code: int = 200, **context):
    context.update(user=user, csrf_token=ensure_csrf_token(request))
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def login_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(f"/login?next={quote(request.url.path)}", status_code=303)


@router.get("/")
def home(user: User | None = Depends(get_optional_user)):
    return RedirectResponse("/dashboard" if user else "/login", status_code=303)


@router.get("/login")
def login_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "login.html", None)


@router.get("/signup")
def signup_page(request: Request, user: User | None = Depends(get_optional_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "signup.html", None)


_SIMPLE_PAGES = {
    "/dashboard": ("dashboard.html", "dashboard"),
    "/friends": ("friends.html", "friends"),
    "/groups": ("friend_groups.html", "groups"),
    "/trips": ("trips.html", "trips"),
    "/account": ("account.html", "account"),
}


def _simple_page(template: str, nav: str):
    def page(request: Request, user: User | None = Depends(get_optional_user)):
        if user is None:
            return login_redirect(request)
        return render(request, template, user, nav=nav)

    return page


for _path, (_template, _nav) in _SIMPLE_PAGES.items():
    router.add_api_route(_path, _simple_page(_template, _nav), methods=["GET"])


def _trip_page(template: str):
    def page(trip_id: int, request: Request, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
        if user is None:
            return login_redirect(request)
        try:
            trip = get_trip_for_member(db, trip_id, user)
        except AppError:
            return render(request, "not_found.html", user, status_code=404, nav="trips")
        return render(request, template, user, nav="trips", trip=trip, is_owner=trip.owner_id == user.id)

    return page


router.add_api_route("/trips/{trip_id}", _trip_page("trip_detail.html"), methods=["GET"])
router.add_api_route("/trips/{trip_id}/budget", _trip_page("budget.html"), methods=["GET"])
router.add_api_route("/trips/{trip_id}/locations", _trip_page("locations.html"), methods=["GET"])
