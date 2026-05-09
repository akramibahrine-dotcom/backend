from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.order import (
    CreateOrderRequest,
    CreateOrderResponse,
    ValidateOrderRequest,
    ValidateOrderResponse,
)
from app.services.orders import create_order, validate_order

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
    return await create_order(req, request, db)
