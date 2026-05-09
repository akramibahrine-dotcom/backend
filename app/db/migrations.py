from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.logging import get_logger

logger = get_logger(__name__)


def run_migrations() -> None:
    """Run Alembic upgrade head synchronously (called from startup)."""
    alembic_ini = Path(__file__).parent.parent.parent / "alembic.ini"
    cfg = Config(str(alembic_ini))
    try:
        command.upgrade(cfg, "head")
        logger.info("database_migrations_complete")
    except Exception as exc:
        logger.error("database_migrations_failed", error=str(exc))
        raise


async def run_migrations_async() -> None:
    """Wrap sync Alembic run in a thread so it doesn't block event loop."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_migrations)
