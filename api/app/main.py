import logging
import time
import urllib.request
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.alerts import get_provider
from app.services.bootstrap import bootstrap_admin, ensure_bootstrap_device
from app.services.storage import ensure_bucket
from app.core.config import settings

logger = logging.getLogger("sentinel.api")

VALIDATION_TEXT = {
    "Field required": "campo obligatorio",
    "value is not a valid email address": "correo no válido",
    "Input should be a valid string": "texto no válido",
    "Input should be a valid integer": "número no válido",
    "Input should be a valid boolean": "valor no válido",
    "Input should be a valid UUID": "identificador no válido",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    bootstrap_admin()
    ensure_bootstrap_device()
    ensure_bucket()
    logger.info(
        "alert provider=%s telegram=%s",
        get_provider().name,
        "configured" if settings.telegram_bot_token else "off",
    )
    yield


app = FastAPI(title="SentinelAI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    logger.info("%s %s %s %sms", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    messages: list[str] = []
    for error in exc.errors():
        message = str(error.get("msg", ""))
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        message = VALIDATION_TEXT.get(message, message)
        location = [str(part) for part in error.get("loc", []) if part not in ("body", "query")]
        place = ".".join(location)
        messages.append(f"{place}: {message}" if place else message)
    detail = "Datos inválidos. " + " ".join(messages) if messages else "Datos inválidos"
    return JSONResponse(status_code=422, content={"detail": detail})


def _check_postgres(db: Session) -> str:
    db.execute(text("SELECT 1"))
    return "ok"


def _check_redis() -> str:
    client = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
    try:
        client.ping()
    finally:
        client.close()
    return "ok"


def _check_minio() -> str:
    scheme = "https" if settings.minio_secure else "http"
    with urllib.request.urlopen(f"{scheme}://{settings.minio_endpoint}/minio/health/live", timeout=2) as response:
        if response.status != 200:
            raise RuntimeError("minio unhealthy")
    return "ok"


@app.get("/health")
def health() -> JSONResponse:
    checks: dict[str, str] = {}
    db = SessionLocal()
    try:
        try:
            checks["postgres"] = _check_postgres(db)
        except Exception:
            logger.exception("postgres health check failed")
            checks["postgres"] = "error"
    finally:
        db.close()
    try:
        checks["redis"] = _check_redis()
    except Exception:
        logger.exception("redis health check failed")
        checks["redis"] = "error"
    try:
        checks["minio"] = _check_minio()
    except Exception:
        logger.exception("minio health check failed")
        checks["minio"] = "error"
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(status_code=200 if healthy else 503, content={"status": "ok" if healthy else "degraded", **checks})
