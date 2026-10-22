import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("tripzy")


class AppError(Exception):
    """An expected error returned to the client as {"detail", "code"[, "field"]}."""

    def __init__(self, status_code: int, detail: str, code: str, field: str | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code
        self.field = field


def not_found(what: str = "Resource") -> AppError:
    return AppError(404, f"{what} not found", "NOT_FOUND")


def forbidden(detail: str = "You don't have permission to do that") -> AppError:
    return AppError(403, detail, "FORBIDDEN")


_FRIENDLY = {
    "missing": "This field is required",
    "string_too_short": "This field is required",
    "json_invalid": "Request body is not valid JSON",
}


def _friendly_message(error: dict) -> str:
    kind = error.get("type", "")
    if kind == "string_too_short" and error.get("ctx", {}).get("min_length", 1) > 1:
        return f"Must be at least {error['ctx']['min_length']} characters"
    if kind == "string_too_long":
        return f"Must be at most {error['ctx']['max_length']} characters"
    if kind == "value_error" and "email" in str(error.get("msg", "")).lower():
        return "Enter a valid email address"
    if kind.startswith("date"):
        return "Enter a valid date (YYYY-MM-DD)"
    if kind in ("int_parsing", "int_type"):
        return "Must be a whole number"
    return _FRIENDLY.get(kind, str(error.get("msg", "Invalid value")))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError):
        body = {"detail": exc.detail, "code": exc.code}
        if exc.field:
            body["field"] = exc.field
        return JSONResponse(body, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
            errors.append({"field": ".".join(loc) or None, "message": _friendly_message(err)})
        if any((e["field"] or "").split(".")[0] == "amount" for e in errors):
            return JSONResponse(
                {"detail": "Enter a valid amount", "code": "INVALID_EXPENSE_AMOUNT", "field": "amount", "errors": errors},
                status_code=422,
            )
        first = errors[0] if errors else {"field": None, "message": "Invalid request"}
        label = (first["field"] or "").split(".")[0].replace("_", " ").capitalize()
        detail = f"{label}: {first['message']}" if label else first["message"]
        body = {"detail": detail, "code": "VALIDATION_ERROR", "errors": errors}
        if first["field"]:
            body["field"] = first["field"]
        return JSONResponse(body, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_request: Request, exc: StarletteHTTPException):
        codes = {401: "NOT_AUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse(
            {"detail": exc.detail, "code": codes.get(exc.status_code, "HTTP_ERROR")},
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception):
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse({"detail": "Something went wrong. Please try again.", "code": "INTERNAL_ERROR"}, status_code=500)
