from __future__ import annotations

import asyncio
import time
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 3


def run_migrations() -> None:
    """Run Alembic upgrade head synchronously with retries for DB readiness."""
    alembic_ini = Path(__file__).parent.parent.parent / "alembic.ini"
    cfg = Config(str(alembic_ini))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            command.upgrade(cfg, "head")
            logger.info("database_migrations_complete")
            return
        except Exception as exc:
            logger.warning(
                "database_migration_attempt_failed",
                attempt=attempt,
                max_retries=MAX_RETRIES,
                error=str(exc),
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    logger.error(
        "database_migrations_failed_all_retries",
        max_retries=MAX_RETRIES,
    )


async def run_migrations_async() -> None:
    """Wrap sync Alembic run in a thread so it doesn't block event loop."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_migrations)
