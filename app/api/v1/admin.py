from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, case, desc, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.admin_auth import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.event import AdminAccessRule, AdminLoginEvent, SiteClick, StoreTranslationOverride
from app.models.fraud import FraudCheck
from app.models.order import Order, OrderItem
from app.schemas.admin import (
    AdminAccessRuleInput,
    AdminAccessRuleResponse,
    AdminAccessRulesResponse,
    AdminLoginEventsResponse,
    AdminMetricsResponse,
    AdminOrderDetail,
    AdminOrderItem,
    AdminOrderListItem,
    AdminOrdersResponse,
    AdminSessionResponse,
    TrackClickRequest,
    TrackClickResponse,
    TranslationOverrideInput,
    TranslationOverrideResponse,
    TranslationOverridesResponse,
)
from app.services import geoip as geoip_svc
from app.services import maxmind as maxmind_svc
from app.services.orders import get_client_ip
from app.services.products import BUNDLE_PRICES, PRODUCTS, UPSELL_PRICE_SAR

router = APIRouter()


def _date_window(start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    end_dt = end or now
    start_dt = start or (end_dt - timedelta(days=7))
    return start_dt, end_dt


def _today_window() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0), now


def _classify_user_agent(user_agent: str | None) -> dict[str, str]:
    ua = (user_agent or "").lower()
    if "ipad" in ua or "tablet" in ua:
        device = "tablet"
    elif "mobile" in ua or "iphone" in ua or "android" in ua:
        device = "mobile"
    else:
        device = "desktop"

    if "edg/" in ua:
        browser = "Edge"
    elif "chrome/" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "safari/" in ua and "chrome/" not in ua:
        browser = "Safari"
    elif "firefox/" in ua:
        browser = "Firefox"
    else:
        browser = "Unknown"

    if "windows" in ua:
        os_name = "Windows"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        os_name = "iOS"
    elif "android" in ua:
        os_name = "Android"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "macOS"
    else:
        os_name = "Unknown"

    return {"device_type": device, "browser": browser, "os": os_name}


def _valid_order_filter(start: datetime, end: datetime):
    return and_(
        Order.created_at >= start,
        Order.created_at <= end,
        Order.is_test_order.is_(False),
        FraudCheck.country_iso_code == "SA",
        FraudCheck.decision.in_(["allowed", "allowed_test", "error_allow"]),
        or_(FraudCheck.is_anonymous_proxy.is_(False), FraudCheck.is_anonymous_proxy.is_(None)),
        or_(FraudCheck.is_anonymous_vpn.is_(False), FraudCheck.is_anonymous_vpn.is_(None)),
        or_(FraudCheck.is_hosting_provider.is_(False), FraudCheck.is_hosting_provider.is_(None)),
        or_(FraudCheck.is_public_proxy.is_(False), FraudCheck.is_public_proxy.is_(None)),
        or_(FraudCheck.is_residential_proxy.is_(False), FraudCheck.is_residential_proxy.is_(None)),
        or_(FraudCheck.is_tor_exit_node.is_(False), FraudCheck.is_tor_exit_node.is_(None)),
    )


async def _period_stats(db: AsyncSession, start: datetime, end: datetime) -> dict:
    clicks = await db.scalar(
        select(func.count(SiteClick.id)).where(
            SiteClick.created_at >= start,
            SiteClick.created_at <= end,
            SiteClick.is_valid_ksa.is_(True),
        )
    ) or 0
    visitors = await db.scalar(
        select(func.count(distinct(SiteClick.session_id))).where(
            SiteClick.created_at >= start,
            SiteClick.created_at <= end,
            SiteClick.is_valid_ksa.is_(True),
            SiteClick.session_id.is_not(None),
        )
    ) or 0
    order_filter = _valid_order_filter(start, end)
    row = (
        await db.execute(
            select(func.count(distinct(Order.id)), func.coalesce(func.sum(Order.total_sar), 0))
            .join(FraudCheck, FraudCheck.order_id == Order.id)
            .where(order_filter)
        )
    ).one()
    orders = int(row[0] or 0)
    revenue = int(row[1] or 0)
    return {
        "visitors": int(visitors),
        "clicks": int(clicks),
        "orders": orders,
        "revenue_sar": revenue,
        "average_order_value_sar": round(revenue / orders, 2) if orders else 0.0,
        "conversion_rate": round((orders / clicks) * 100, 2) if clicks else 0.0,
    }


async def _product_metrics(db: AsyncSession, start: datetime, end: datetime, order_filter) -> list[dict]:
    product_views = {
        row.product_id: int(row.views or 0)
        for row in (
            await db.execute(
                select(SiteClick.product_id, func.count(SiteClick.id).label("views"))
                .where(
                    SiteClick.created_at >= start,
                    SiteClick.created_at <= end,
                    SiteClick.is_valid_ksa.is_(True),
                    SiteClick.event_name == "view_content",
                    SiteClick.product_id.is_not(None),
                )
                .group_by(SiteClick.product_id)
            )
        ).all()
    }
    add_to_cart = {
        row.product_id: int(row.count or 0)
        for row in (
            await db.execute(
                select(SiteClick.product_id, func.count(SiteClick.id).label("count"))
                .where(
                    SiteClick.created_at >= start,
                    SiteClick.created_at <= end,
                    SiteClick.is_valid_ksa.is_(True),
                    SiteClick.event_name == "add_to_cart",
                    SiteClick.product_id.is_not(None),
                )
                .group_by(SiteClick.product_id)
            )
        ).all()
    }
    item_rows = (
        await db.execute(
            select(
                OrderItem.product_id,
                func.count(distinct(Order.id)).label("orders"),
                func.sum(OrderItem.quantity).label("units"),
                func.sum(OrderItem.bundle_price_sar).label("revenue_sar"),
                func.sum(case((OrderItem.source == "cart_cross_sell", OrderItem.quantity), else_=0)).label("cross_sell_units"),
                func.sum(case((OrderItem.source == "checkout_upsell", OrderItem.quantity), else_=0)).label("upsell_units"),
            )
            .join(Order, Order.id == OrderItem.order_id)
            .join(FraudCheck, FraudCheck.order_id == Order.id)
            .where(order_filter)
            .group_by(OrderItem.product_id)
        )
    ).all()
    item_metrics = {
        row.product_id: {
            "orders": int(row.orders or 0),
            "units": int(row.units or 0),
            "revenue_sar": int(row.revenue_sar or 0),
            "cross_sell_units": int(row.cross_sell_units or 0),
            "upsell_units": int(row.upsell_units or 0),
        }
        for row in item_rows
    }

    products = []
    for product in PRODUCTS.values():
        views = product_views.get(product.product_id, 0)
        metrics = item_metrics.get(product.product_id, {})
        product_orders = metrics.get("orders", 0)
        products.append(
            {
                "id": product.product_id,
                "slug": product.slug,
                "sku": product.sku,
                "name_ar": product.name_ar,
                "concern_ar": product.concern_ar,
                "bundle_prices_sar": BUNDLE_PRICES,
                "upsell_price_sar": UPSELL_PRICE_SAR,
                "upsell_product_id": product.upsell_product_id,
                "cross_sell_product_ids": list(product.cross_sell_product_ids),
                "views": views,
                "add_to_cart": add_to_cart.get(product.product_id, 0),
                "orders": product_orders,
                "units": metrics.get("units", 0),
                "revenue_sar": metrics.get("revenue_sar", 0),
                "conversion_rate": round((product_orders / views) * 100, 2) if views else 0.0,
                "cross_sell_units": metrics.get("cross_sell_units", 0),
                "upsell_units": metrics.get("upsell_units", 0),
            }
        )
    return products


@router.post("/analytics/clicks", response_model=TrackClickResponse)
async def track_click(
    req: TrackClickRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrackClickResponse:
    settings = get_settings()
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    device = _classify_user_agent(user_agent)

    country = await geoip_svc.lookup_country(client_ip)
    if country and country not in settings.get_analytics_allowed_countries():
        return TrackClickResponse(accepted=False, reason="country_not_allowed")

    quality = await maxmind_svc.check_ip_quality(
        ip_address=client_ip,
        user_agent=user_agent,
        allowed_countries=settings.get_analytics_allowed_countries(),
    )
    if not quality.allowed:
        return TrackClickResponse(accepted=False, reason=quality.reason)

    utm = req.utm
    db.add(
        SiteClick(
            session_id=req.session_id,
            event_name=req.event_name,
            page_url=req.page_url,
            referrer=req.referrer,
            product_id=req.product_id,
            source=req.source,
            device_type=req.device_type or device["device_type"],
            browser=req.browser or device["browser"],
            os=req.os or device["os"],
            utm_source=utm.source if utm else None,
            utm_medium=utm.medium if utm else None,
            utm_campaign=utm.campaign if utm else None,
            utm_content=utm.content if utm else None,
            utm_term=utm.term if utm else None,
            ip_address=client_ip,
            user_agent=user_agent,
            country_iso_code=quality.country_iso_code or country,
            risk_score=quality.risk_score,
            ip_risk=quality.ip_risk,
            is_valid_ksa=True,
            invalid_reason=None,
        )
    )
    await db.commit()
    return TrackClickResponse(accepted=True)


@router.post("/admin/session", response_model=AdminSessionResponse)
async def admin_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    username: Annotated[str, Depends(require_admin)],
) -> AdminSessionResponse:
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    device = _classify_user_agent(user_agent)
    country = await geoip_svc.lookup_country(client_ip)
    db.add(
        AdminLoginEvent(
            username=username,
            ip_address=client_ip,
            user_agent=user_agent,
            device_type=device["device_type"],
            browser=device["browser"],
            os=device["os"],
            country_iso_code=country,
            status="success",
            last_seen_at=datetime.now(UTC),
        )
    )
    await db.commit()
    return AdminSessionResponse(ok=True)


@router.get("/admin/metrics", response_model=AdminMetricsResponse, dependencies=[Depends(require_admin)])
async def admin_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> AdminMetricsResponse:
    start_dt, end_dt = _date_window(start, end)
    today_start, today_end = _today_window()

    clicks = await db.scalar(
        select(func.count(SiteClick.id)).where(
            SiteClick.created_at >= start_dt,
            SiteClick.created_at <= end_dt,
            SiteClick.is_valid_ksa.is_(True),
        )
    ) or 0
    unique_sessions = await db.scalar(
        select(func.count(distinct(SiteClick.session_id))).where(
            SiteClick.created_at >= start_dt,
            SiteClick.created_at <= end_dt,
            SiteClick.is_valid_ksa.is_(True),
            SiteClick.session_id.is_not(None),
        )
    ) or 0
    live_cutoff = datetime.now(UTC) - timedelta(minutes=5)
    live_visitors = await db.scalar(
        select(func.count(distinct(SiteClick.session_id))).where(
            SiteClick.created_at >= live_cutoff,
            SiteClick.is_valid_ksa.is_(True),
            SiteClick.session_id.is_not(None),
        )
    ) or 0

    order_filter = _valid_order_filter(start_dt, end_dt)
    order_row = (
        await db.execute(
            select(func.count(distinct(Order.id)), func.coalesce(func.sum(Order.total_sar), 0))
            .join(FraudCheck, FraudCheck.order_id == Order.id)
            .where(order_filter)
        )
    ).one()
    orders = int(order_row[0] or 0)
    revenue = int(order_row[1] or 0)
    average_order_value = round(revenue / orders, 2) if orders else 0.0
    conversion_rate = round((orders / clicks) * 100, 2) if clicks else 0.0
    new_customers = await db.scalar(
        select(func.count(distinct(Order.customer_phone_e164)))
        .join(FraudCheck, FraudCheck.order_id == Order.id)
        .where(order_filter)
    ) or 0

    today_stats = await _period_stats(db, today_start, today_end)
    all_time_stats = await _period_stats(db, datetime(2020, 1, 1, tzinfo=UTC), today_end)

    cross_sell_orders = await db.scalar(
        select(func.count(distinct(Order.id)))
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(FraudCheck, FraudCheck.order_id == Order.id)
        .where(order_filter, OrderItem.source == "cart_cross_sell")
    ) or 0
    upsell_orders = await db.scalar(
        select(func.count(distinct(Order.id)))
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(FraudCheck, FraudCheck.order_id == Order.id)
        .where(order_filter, OrderItem.source == "checkout_upsell")
    ) or 0
    cross_sell_rate = round((cross_sell_orders / orders) * 100, 2) if orders else 0.0
    upsell_rate = round((upsell_orders / orders) * 100, 2) if orders else 0.0

    rejected_attempts = await db.scalar(
        select(func.count(FraudCheck.id)).where(
            FraudCheck.created_at >= start_dt,
            FraudCheck.created_at <= end_dt,
            FraudCheck.decision == "rejected",
        )
    ) or 0

    top_products = [
        {
            "product_id": row.product_id,
            "product_name_ar": row.product_name_ar,
            "quantity": int(row.quantity or 0),
            "revenue_sar": int(row.revenue_sar or 0),
        }
        for row in (
            await db.execute(
                select(
                    OrderItem.product_id,
                    OrderItem.product_name_ar,
                    func.sum(OrderItem.quantity).label("quantity"),
                    func.sum(OrderItem.bundle_price_sar).label("revenue_sar"),
                )
                .join(Order, Order.id == OrderItem.order_id)
                .join(FraudCheck, FraudCheck.order_id == Order.id)
                .where(order_filter)
                .group_by(OrderItem.product_id, OrderItem.product_name_ar)
                .order_by(desc("revenue_sar"))
                .limit(8)
            )
        ).all()
    ]
    products = await _product_metrics(db, start_dt, end_dt, order_filter)

    daily_clicks = {
        str(row.day): int(row.count or 0)
        for row in (
            await db.execute(
                select(func.date(SiteClick.created_at).label("day"), func.count(SiteClick.id).label("count"))
                .where(
                    SiteClick.created_at >= start_dt,
                    SiteClick.created_at <= end_dt,
                    SiteClick.is_valid_ksa.is_(True),
                )
                .group_by("day")
            )
        ).all()
    }
    daily_orders = {
        str(row.day): {"orders": int(row.orders or 0), "revenue_sar": int(row.revenue_sar or 0)}
        for row in (
            await db.execute(
                select(
                    func.date(Order.created_at).label("day"),
                    func.count(distinct(Order.id)).label("orders"),
                    func.coalesce(func.sum(Order.total_sar), 0).label("revenue_sar"),
                )
                .join(FraudCheck, FraudCheck.order_id == Order.id)
                .where(order_filter)
                .group_by("day")
            )
        ).all()
    }
    day_keys = sorted(set(daily_clicks) | set(daily_orders))
    daily = [
        {
            "date": day,
            "clicks": daily_clicks.get(day, 0),
            "orders": daily_orders.get(day, {}).get("orders", 0),
            "revenue_sar": daily_orders.get(day, {}).get("revenue_sar", 0),
        }
        for day in day_keys
    ]

    campaign_breakdown = [
        {"campaign": row.campaign or "Direct / unknown", "orders": int(row.orders or 0), "revenue_sar": int(row.revenue_sar or 0)}
        for row in (
            await db.execute(
                select(
                    Order.utm_campaign.label("campaign"),
                    func.count(distinct(Order.id)).label("orders"),
                    func.coalesce(func.sum(Order.total_sar), 0).label("revenue_sar"),
                )
                .join(FraudCheck, FraudCheck.order_id == Order.id)
                .where(order_filter)
                .group_by(Order.utm_campaign)
                .order_by(desc("revenue_sar"))
                .limit(8)
            )
        ).all()
    ]

    traffic_sources = [
        {"source": row.source or "Direct / unknown", "clicks": int(row.clicks or 0)}
        for row in (
            await db.execute(
                select(SiteClick.utm_source.label("source"), func.count(SiteClick.id).label("clicks"))
                .where(
                    SiteClick.created_at >= start_dt,
                    SiteClick.created_at <= end_dt,
                    SiteClick.is_valid_ksa.is_(True),
                )
                .group_by(SiteClick.utm_source)
                .order_by(desc("clicks"))
                .limit(8)
            )
        ).all()
    ]
    device_breakdown = [
        {"device": row.device or "Unknown", "visitors": int(row.visitors or 0), "clicks": int(row.clicks or 0)}
        for row in (
            await db.execute(
                select(
                    SiteClick.device_type.label("device"),
                    func.count(distinct(SiteClick.session_id)).label("visitors"),
                    func.count(SiteClick.id).label("clicks"),
                )
                .where(
                    SiteClick.created_at >= start_dt,
                    SiteClick.created_at <= end_dt,
                    SiteClick.is_valid_ksa.is_(True),
                )
                .group_by(SiteClick.device_type)
                .order_by(desc("clicks"))
            )
        ).all()
    ]
    country_breakdown = [
        {"country": row.country or "Unknown", "visitors": int(row.visitors or 0), "clicks": int(row.clicks or 0)}
        for row in (
            await db.execute(
                select(
                    SiteClick.country_iso_code.label("country"),
                    func.count(distinct(SiteClick.session_id)).label("visitors"),
                    func.count(SiteClick.id).label("clicks"),
                )
                .where(
                    SiteClick.created_at >= start_dt,
                    SiteClick.created_at <= end_dt,
                    SiteClick.is_valid_ksa.is_(True),
                )
                .group_by(SiteClick.country_iso_code)
                .order_by(desc("clicks"))
            )
        ).all()
    ]

    return AdminMetricsResponse(
        start_date=start_dt,
        end_date=end_dt,
        clicks=clicks,
        unique_sessions=unique_sessions,
        orders=orders,
        revenue_sar=revenue,
        average_order_value_sar=average_order_value,
        conversion_rate=conversion_rate,
        rejected_attempts=rejected_attempts,
        today=today_stats,
        all_time=all_time_stats,
        live_visitors=live_visitors,
        new_customers=new_customers,
        cross_sell_rate=cross_sell_rate,
        upsell_rate=upsell_rate,
        top_products=top_products,
        products=products,
        daily=daily,
        campaign_breakdown=campaign_breakdown,
        traffic_sources=traffic_sources,
        device_breakdown=device_breakdown,
        country_breakdown=country_breakdown,
    )


@router.get("/admin/orders", response_model=AdminOrdersResponse, dependencies=[Depends(require_admin)])
async def admin_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AdminOrdersResponse:
    start_dt, end_dt = _date_window(start, end)
    rows = (
        await db.execute(
            select(Order, FraudCheck)
            .join(FraudCheck, FraudCheck.order_id == Order.id, isouter=True)
            .where(Order.created_at >= start_dt, Order.created_at <= end_dt)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
    ).all()
    return AdminOrdersResponse(
        orders=[_order_list_item(order, fraud) for order, fraud in rows]
    )


@router.get("/admin/orders/{order_id}", response_model=AdminOrderDetail, dependencies=[Depends(require_admin)])
async def admin_order_detail(
    order_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminOrderDetail:
    order = (
        await db.execute(
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.fraud_checks),
                selectinload(Order.tracking_events),
                selectinload(Order.webhook_deliveries),
            )
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    fraud = order.fraud_checks[-1] if order.fraud_checks else None
    base = _order_list_item(order, fraud).model_dump()
    return AdminOrderDetail(
        **base,
        customer_phone_e164=order.customer_phone_e164,
        subtotal_sar=order.subtotal_sar,
        shipping_sar=order.shipping_sar,
        display_currency=order.display_currency,
        display_total=float(order.display_total) if isinstance(order.display_total, Decimal) else order.display_total,
        landing_page_url=order.landing_page_url,
        page_url=order.page_url,
        ip_address=order.ip_address,
        user_agent=order.user_agent,
        utm_medium=order.utm_medium,
        utm_content=order.utm_content,
        utm_term=order.utm_term,
        risk_score=float(fraud.risk_score) if fraud and fraud.risk_score is not None else None,
        ip_risk=float(fraud.ip_risk) if fraud and fraud.ip_risk is not None else None,
        items=[
            AdminOrderItem(
                product_id=item.product_id,
                product_name_ar=item.product_name_ar,
                quantity=item.quantity,
                bundle_price_sar=item.bundle_price_sar,
                source=item.source,
            )
            for item in order.items
        ],
        tracking_events=[
            {
                "platform": event.platform,
                "event_name": event.event_name,
                "status": event.status,
                "error": event.error,
                "created_at": event.created_at.isoformat(),
            }
            for event in order.tracking_events
        ],
        webhook_deliveries=[
            {
                "destination": delivery.destination,
                "status": delivery.status,
                "attempts": delivery.attempts,
                "last_error": delivery.last_error,
            }
            for delivery in order.webhook_deliveries
        ],
    )


@router.get("/admin/logins", response_model=AdminLoginEventsResponse, dependencies=[Depends(require_admin)])
async def admin_logins(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> AdminLoginEventsResponse:
    live_cutoff = datetime.now(UTC) - timedelta(minutes=15)
    rows = (
        await db.execute(
            select(AdminLoginEvent)
            .order_by(AdminLoginEvent.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    live_rows = (
        await db.execute(
            select(AdminLoginEvent)
            .where(AdminLoginEvent.last_seen_at >= live_cutoff)
            .order_by(AdminLoginEvent.last_seen_at.desc())
            .limit(20)
        )
    ).scalars().all()
    return AdminLoginEventsResponse(
        logins=[_login_event_dict(row) for row in rows],
        live=[_login_event_dict(row) for row in live_rows],
    )


@router.get("/admin/access-rules", response_model=AdminAccessRulesResponse, dependencies=[Depends(require_admin)])
async def list_access_rules(db: Annotated[AsyncSession, Depends(get_db)]) -> AdminAccessRulesResponse:
    rows = (
        await db.execute(select(AdminAccessRule).order_by(AdminAccessRule.created_at.desc()))
    ).scalars().all()
    return AdminAccessRulesResponse(rules=[_access_rule_response(row) for row in rows])


@router.post(
    "/admin/access-rules",
    response_model=AdminAccessRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_access_rule(
    req: AdminAccessRuleInput,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminAccessRuleResponse:
    row = AdminAccessRule(**req.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _access_rule_response(row)


@router.put("/admin/access-rules/{rule_id}", response_model=AdminAccessRuleResponse, dependencies=[Depends(require_admin)])
async def update_access_rule(
    rule_id: str,
    req: AdminAccessRuleInput,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminAccessRuleResponse:
    row = await db.get(AdminAccessRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Access rule not found.")
    for key, value in req.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return _access_rule_response(row)


@router.delete(
    "/admin/access-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_access_rule(
    rule_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await db.get(AdminAccessRule, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Access rule not found.")
    await db.delete(row)
    await db.commit()


@router.get("/admin/translations", response_model=TranslationOverridesResponse, dependencies=[Depends(require_admin)])
async def list_translations(db: Annotated[AsyncSession, Depends(get_db)]) -> TranslationOverridesResponse:
    rows = (
        await db.execute(select(StoreTranslationOverride).order_by(StoreTranslationOverride.translation_key.asc()))
    ).scalars().all()
    return TranslationOverridesResponse(translations=[_translation_response(row) for row in rows])


@router.post(
    "/admin/translations",
    response_model=TranslationOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def create_translation(
    req: TranslationOverrideInput,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TranslationOverrideResponse:
    row = StoreTranslationOverride(**req.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _translation_response(row)


@router.put("/admin/translations/{translation_id}", response_model=TranslationOverrideResponse, dependencies=[Depends(require_admin)])
async def update_translation(
    translation_id: str,
    req: TranslationOverrideInput,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TranslationOverrideResponse:
    row = await db.get(StoreTranslationOverride, translation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Translation override not found.")
    for key, value in req.model_dump().items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return _translation_response(row)


@router.delete(
    "/admin/translations/{translation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_translation(
    translation_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    row = await db.get(StoreTranslationOverride, translation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Translation override not found.")
    await db.delete(row)
    await db.commit()


@router.get("/store/translations")
async def public_translations(db: Annotated[AsyncSession, Depends(get_db)], locale: str = "ar") -> dict:
    rows = (
        await db.execute(
            select(StoreTranslationOverride).where(
                StoreTranslationOverride.locale == locale,
                StoreTranslationOverride.enabled.is_(True),
            )
        )
    ).scalars().all()
    return {row.translation_key: row.value for row in rows}


@router.get("/store/access")
async def public_store_access(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    device = _classify_user_agent(user_agent)
    country = await geoip_svc.lookup_country(client_ip)
    rows = (
        await db.execute(
            select(AdminAccessRule).where(
                AdminAccessRule.enabled.is_(True),
            )
        )
    ).scalars().all()

    block_rules = [rule for rule in rows if rule.action == "block"]
    allow_rules = [rule for rule in rows if rule.action == "allow"]

    for rule in block_rules:
        value = rule.value.strip().lower()
        if rule.rule_type == "ip" and client_ip and value == client_ip.lower():
            return {"allowed": False, "reason": rule.name, "rule_type": rule.rule_type}
        if rule.rule_type == "country" and country and value == country.lower():
            return {"allowed": False, "reason": rule.name, "rule_type": rule.rule_type}
        if rule.rule_type == "device" and value == device["device_type"].lower():
            return {"allowed": False, "reason": rule.name, "rule_type": rule.rule_type}

    if allow_rules and not any(_access_rule_matches(rule, client_ip, country, device["device_type"]) for rule in allow_rules):
        return {"allowed": False, "reason": "not_in_allowlist", "rule_type": "allowlist"}

    return {
        "allowed": True,
        "country_iso_code": country,
        "device_type": device["device_type"],
    }


def _order_list_item(order: Order, fraud: FraudCheck | None) -> AdminOrderListItem:
    return AdminOrderListItem(
        id=order.id,
        public_order_number=order.public_order_number,
        status=order.status,
        customer_name=order.customer_name,
        customer_phone_local=order.customer_phone_local,
        total_sar=order.total_sar,
        is_test_order=order.is_test_order,
        created_at=order.created_at,
        utm_source=order.utm_source,
        utm_campaign=order.utm_campaign,
        country_iso_code=fraud.country_iso_code if fraud else None,
        fraud_decision=fraud.decision if fraud else None,
        fraud_reason=fraud.reason if fraud else None,
    )


def _login_event_dict(row: AdminLoginEvent) -> dict:
    return {
        "id": row.id,
        "username": row.username,
        "ip_address": row.ip_address,
        "country_iso_code": row.country_iso_code,
        "device_type": row.device_type,
        "browser": row.browser,
        "os": row.os,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "last_seen_at": row.last_seen_at.isoformat(),
    }


def _access_rule_matches(rule: AdminAccessRule, ip_address: str | None, country: str | None, device_type: str) -> bool:
    value = rule.value.strip().lower()
    if rule.rule_type == "ip":
        return bool(ip_address and value == ip_address.lower())
    if rule.rule_type == "country":
        return bool(country and value == country.lower())
    if rule.rule_type == "device":
        return value == device_type.lower()
    return False


def _access_rule_response(row: AdminAccessRule) -> AdminAccessRuleResponse:
    return AdminAccessRuleResponse(
        id=row.id,
        name=row.name,
        rule_type=row.rule_type,
        value=row.value,
        action=row.action,
        enabled=row.enabled,
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _translation_response(row: StoreTranslationOverride) -> TranslationOverrideResponse:
    return TranslationOverrideResponse(
        id=row.id,
        locale=row.locale,
        translation_key=row.translation_key,
        value=row.value,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
