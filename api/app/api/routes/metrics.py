import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import DEFAULT_TIMEZONE
from app.db.session import get_db
from app.models.entities import Event, UsageRecord, User
from app.schemas.metrics import DayCount, MetricsRead, PricingRead, PricingWrite
from app.services.pricing import ensure_pricing_plan

router = APIRouter(tags=["metrics"])
logger = logging.getLogger("sentinel.api")
GUATEMALA = ZoneInfo(DEFAULT_TIMEZONE)


def month_bounds(moment: datetime | None = None) -> tuple[date, date, datetime, datetime]:
    local = (moment or datetime.now(GUATEMALA)).astimezone(GUATEMALA)
    first = local.date().replace(day=1)
    if first.month == 12:
        next_month = date(first.year + 1, 1, 1)
    else:
        next_month = date(first.year, first.month + 1, 1)
    start_at = datetime.combine(first, time.min, tzinfo=GUATEMALA)
    end_at = datetime.combine(next_month, time.min, tzinfo=GUATEMALA)
    return first, next_month, start_at, end_at


def previous_month_bounds(first: date) -> tuple[date, date]:
    previous_end = first
    previous_start = (first - timedelta(days=1)).replace(day=1)
    return previous_start, previous_end


@router.get("/metrics", response_model=MetricsRead)
def read_metrics(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MetricsRead:
    plan = ensure_pricing_plan(db, user.organization_id)
    first, next_month, start_at, end_at = month_bounds()
    local_day = cast(func.timezone(DEFAULT_TIMEZONE, Event.occurred_at), Date)
    counted = db.execute(
        select(local_day, func.count())
        .where(
            Event.organization_id == user.organization_id,
            Event.occurred_at >= start_at,
            Event.occurred_at < end_at,
        )
        .group_by(local_day)
    ).all()
    by_day: dict[date, int] = {}
    for day, count in counted:
        if isinstance(day, datetime):
            day = day.date()
        by_day[day] = int(count)
    days: list[DayCount] = []
    cursor = first
    while cursor < next_month:
        days.append(DayCount(date=cursor, count=int(by_day.get(cursor, 0))))
        cursor += timedelta(days=1)
    reviewed = list(
        db.scalars(
            select(Event).where(
                Event.organization_id == user.organization_id,
                Event.reviewed_at.is_not(None),
                Event.occurred_at >= start_at,
                Event.occurred_at < end_at,
            )
        )
    )
    deltas = [
        (event.reviewed_at - event.occurred_at).total_seconds()
        for event in reviewed
        if event.reviewed_at is not None
    ]
    average = round(sum(deltas) / len(deltas), 1) if deltas else None
    minutes = db.scalar(
        select(func.coalesce(func.sum(UsageRecord.analyzed_minutes), 0)).where(
            UsageRecord.organization_id == user.organization_id,
            UsageRecord.usage_date >= first,
            UsageRecord.usage_date < next_month,
        )
    )
    analyzed = Decimal(minutes or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rate = Decimal(plan.rate_per_minute)
    cost = (analyzed * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    previous_start = None
    previous_minutes = None
    previous_cost = None
    local_today = datetime.now(GUATEMALA).date()
    if local_today.day <= 3:
        previous_start, previous_end = previous_month_bounds(first)
        earlier = db.scalar(
            select(func.coalesce(func.sum(UsageRecord.analyzed_minutes), 0)).where(
                UsageRecord.organization_id == user.organization_id,
                UsageRecord.usage_date >= previous_start,
                UsageRecord.usage_date < previous_end,
            )
        )
        previous_analyzed = Decimal(earlier or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        previous_minutes = float(previous_analyzed)
        previous_cost = float((previous_analyzed * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return MetricsRead(
        month_start=first,
        events_per_day=days,
        average_response_seconds=average,
        analyzed_minutes=float(analyzed),
        rate_per_minute=float(rate),
        currency=plan.currency,
        estimated_cost=float(cost),
        previous_month_start=previous_start,
        previous_analyzed_minutes=previous_minutes,
        previous_estimated_cost=previous_cost,
    )


@router.put("/pricing", response_model=PricingRead)
def update_pricing(
    payload: PricingWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> PricingRead:
    plan = ensure_pricing_plan(db, user.organization_id)
    plan.rate_per_minute = Decimal(str(payload.rate_per_minute))
    db.commit()
    db.refresh(plan)
    logger.info("pricing updated org=%s rate=%s", user.organization_id, plan.rate_per_minute)
    return PricingRead(rate_per_minute=float(plan.rate_per_minute), currency=plan.currency)
