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


async def _ensure_admin_tables() -> None:
    """Create admin tables with raw SQL as a fallback if Alembic fails."""
    from sqlalchemy import text

    from app.db.session import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS site_clicks (
                id VARCHAR(36) PRIMARY KEY, session_id VARCHAR(100), event_name VARCHAR(80) NOT NULL,
                page_url TEXT, referrer TEXT, product_id VARCHAR(100), source VARCHAR(100),
                device_type VARCHAR(50), browser VARCHAR(100), os VARCHAR(100),
                utm_source VARCHAR(200), utm_medium VARCHAR(200), utm_campaign VARCHAR(200),
                utm_content VARCHAR(200), utm_term VARCHAR(200), ip_address VARCHAR(50),
                user_agent TEXT, country_iso_code VARCHAR(10), risk_score NUMERIC(6,2),
                ip_risk NUMERIC(6,2), is_valid_ksa BOOLEAN NOT NULL DEFAULT FALSE,
                invalid_reason VARCHAR(200), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS admin_login_events (
                id VARCHAR(36) PRIMARY KEY, username VARCHAR(100) NOT NULL, ip_address VARCHAR(50),
                user_agent TEXT, device_type VARCHAR(50), browser VARCHAR(100), os VARCHAR(100),
                country_iso_code VARCHAR(10), status VARCHAR(50) NOT NULL DEFAULT 'success',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(), last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS admin_access_rules (
                id VARCHAR(36) PRIMARY KEY, name VARCHAR(200) NOT NULL, rule_type VARCHAR(50) NOT NULL,
                value VARCHAR(200) NOT NULL, action VARCHAR(50) NOT NULL DEFAULT 'allow',
                enabled BOOLEAN NOT NULL DEFAULT TRUE, notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS store_translation_overrides (
                id VARCHAR(36) PRIMARY KEY, locale VARCHAR(20) NOT NULL DEFAULT 'ar',
                translation_key VARCHAR(300) NOT NULL, value TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.run_migrations_on_start:
        from app.db.migrations import run_migrations_async
        try:
            await run_migrations_async()
        except Exception as exc:
            logger.error("startup_migrations_failed", error=str(exc))
    try:
        await _ensure_admin_tables()
    except Exception as exc:
        logger.error("ensure_admin_tables_failed", error=str(exc))
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
