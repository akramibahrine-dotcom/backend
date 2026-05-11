from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.run_migrations_on_start:
        from app.db.migrations import run_migrations_async
        try:
            await run_migrations_async()
        except Exception as exc:
            logger.error("startup_migrations_failed", error=str(exc))
    logger.info("baytseha_backend_started", env=settings.app_env)
    yield
    logger.info("baytseha_backend_stopped")


app = FastAPI(
    title="Baytseha API",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "server_error", "message": "صار خطأ مؤقت. حاولي مرة ثانية."},
    )
