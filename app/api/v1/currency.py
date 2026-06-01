from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.currency import get_exchange_rates
from app.services import geoip as geoip_svc

router = APIRouter()


class CurrencyRatesResponse(BaseModel):
    base: str
    rates: dict[str, float]


class GeoIPResponse(BaseModel):
    country_code: str | None


def get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.split(",")[0].strip()
    true_client = request.headers.get("true-client-ip")
    if true_client:
        return true_client.split(",")[0].strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "0.0.0.0"


@router.get("/currency/rates", response_model=CurrencyRatesResponse)
async def currency_rates() -> CurrencyRatesResponse:
    rates = await get_exchange_rates()
    return CurrencyRatesResponse(base="SAR", rates=rates)


@router.get("/currency/geo", response_model=GeoIPResponse)
async def currency_geo(request: Request) -> GeoIPResponse:
    # 1. Cloudflare header (100% reliable if proxied)
    cf_country = request.headers.get("cf-ipcountry")
    if cf_country and cf_country != "XX":
        return GeoIPResponse(country_code=cf_country)

    # 2. Fallback to our existing geoip service lookup
    ip = get_client_ip(request)
    iso = await geoip_svc.lookup_country(ip)
    return GeoIPResponse(country_code=iso)
