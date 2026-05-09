from fastapi import APIRouter

from app.api.v1 import currency, health, orders

router = APIRouter(prefix="/api/v1")

router.include_router(health.router, tags=["health"])
router.include_router(orders.router, tags=["orders"])
router.include_router(currency.router, tags=["currency"])
