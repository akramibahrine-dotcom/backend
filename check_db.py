import asyncio
from app.db.session import get_session_factory
from sqlalchemy import select
from app.models.order import Order
from app.models.fraud import FraudCheck

async def main():
    factory = get_session_factory()
    async with factory() as db:
        rows = (await db.execute(
            select(Order, FraudCheck)
            .join(FraudCheck, FraudCheck.order_id == Order.id, isouter=True)
            .order_by(Order.created_at.desc())
            .limit(5)
        )).all()
        for o, f in rows:
            print(f"Order: {o.public_order_number}, Phone: {o.customer_phone_e164}, IP: {o.ip_address}")
            if f:
                print(f"  Fraud: decision={f.decision}, reason={f.reason}, country={f.country_iso_code}")
            else:
                print("  Fraud: None")

asyncio.run(main())