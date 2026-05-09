from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.order import (
    CreateOrderRequest,
    CreateOrderResponse,
    ValidateOrderRequest,
    ValidateOrderResponse,
)
from app.services.orders import create_order, validate_order
from app.services.orders_fallback import create_order_fallback

logger = get_logger(__name__)

router = APIRouter()


@router.post("/orders/validate", response_model=ValidateOrderResponse)
async def validate(
    req: ValidateOrderRequest,
    request: Request,
) -> ValidateOrderResponse:
    return await validate_order(req, request)


@router.post("/orders", response_model=CreateOrderResponse)
async def create(
    req: CreateOrderRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CreateOrderResponse:
    try:
        return await create_order(req, request, db)
    except Exception as exc:
        exc_str = str(exc)
        is_db_error = any(
            phrase in exc_str
            for phrase in [
                "No address associated with hostname",
                "Connection refused",
                "could not connect",
                "connection is closed",
                "server closed the connection",
                "OperationalError",
            ]
        )
        if is_db_error:
            logger.warning("order_db_unavailable_using_fallback", error=exc_str)
            return await create_order_fallback(req, request)
        raise
