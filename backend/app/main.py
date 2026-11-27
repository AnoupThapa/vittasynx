import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.core.errors import AppError
from app.db import new_session


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for key in ("request_id", "method", "path", "status", "duration_ms", "user_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("vittasynx")
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    root.propagate = False


log = logging.getLogger("vittasynx.http")


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_runtime()
    _configure_logging()
    app = FastAPI(title="Vittasynx API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                           allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def request_log(request: Request, call_next):  # noqa: ANN001
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        # Paths and status only: never bodies, query values or financial data.
        log.info("request", extra={"request_id": request_id, "method": request.method, "path": request.url.path,
                                   "status": response.status_code,
                                   "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                                   "user_id": str(getattr(request.state, "user_id", "") or "")})
        response.headers["x-request-id"] = request_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["referrer-policy"] = "same-origin"
        response.headers["x-frame-options"] = "DENY"
        response.headers["cache-control"] = response.headers.get("cache-control", "no-store")
        return response

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code,
                            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request",
                                                                "message": "The request is invalid", "details": details}})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("vittasynx.error").exception("unhandled error", extra={"path": request.url.path})
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error",
                                                                "message": "Something went wrong", "details": None}})

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/health/ready", tags=["health"])
    def ready() -> JSONResponse:
        try:
            with new_session() as db:
                db.execute(text("SELECT 1"))
            return JSONResponse({"status": "ready", "database": "ok"})
        except Exception:  # noqa: BLE001
            return JSONResponse({"status": "unavailable", "database": "error"}, status_code=503)

    from app.api.routers import (
        allocations,
        audit_log,
        auth,
        customers,
        imports,
        invoices,
        organisations,
        payments,
        reports,
    )

    for module in (auth, organisations, customers, imports, invoices, payments, allocations, reports, audit_log):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
