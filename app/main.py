from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import init_db
from app.errors import register_error_handlers
from app.routers import auth, expenses, friend_groups, friends, locations, pages, trips, users

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Tripzy", version="1.0.0", lifespan=lifespan)

# Signed, HTTP-only session cookie. Secure flag is on whenever APP_ENV=production (HTTPS).
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="tripzy_session",
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.is_production,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


register_error_handlers(app)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

for module in (auth, users, friends, friend_groups, trips, expenses, locations, pages):
    app.include_router(module.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
