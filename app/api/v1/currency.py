from fastapi import APIRouter
from pydantic import BaseModel

from app.services.currency import get_exchange_rates

router = APIRouter()


class CurrencyRatesResponse(BaseModel):
    base: str
    rates: dict[str, float]


@router.get("/currency/rates", response_model=CurrencyRatesResponse)
async def currency_rates() -> CurrencyRatesResponse:
    rates = await get_exchange_rates()
    return CurrencyRatesResponse(base="SAR", rates=rates)
