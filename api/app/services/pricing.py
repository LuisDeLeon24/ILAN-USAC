import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import PricingPlan


def ensure_pricing_plan(db: Session, organization_id: uuid.UUID) -> PricingPlan:
    plan = db.scalar(select(PricingPlan).where(PricingPlan.organization_id == organization_id))
    if plan is not None:
        return plan
    plan = PricingPlan(
        organization_id=organization_id,
        currency="GTQ",
        rate_per_minute=Decimal("0"),
        setup_fee=Decimal("0"),
    )
    db.add(plan)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(PricingPlan).where(PricingPlan.organization_id == organization_id))
        if existing is None:
            raise
        return existing
    db.refresh(plan)
    return plan
