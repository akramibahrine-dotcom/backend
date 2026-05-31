import asyncio
from app.db.session import get_session_factory
from app.api.v1.admin import admin_orders
from datetime import datetime, timezone

async def main():
    factory = get_session_factory()
    async with factory() as db:
        res = await admin_orders(db, start=datetime(2020,1,1, tzinfo=timezone.utc), end=datetime(2030,1,1, tzinfo=timezone.utc))
        print(res)

asyncio.run(main())