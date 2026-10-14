import logging

from decimal import Decimal

from sqlalchemy import func, select

from app.core.config import DEFAULT_TIMEZONE, settings
from app.core.security import hash_device_token, hash_password
from app.db.session import SessionLocal
from app.models.entities import Device, Organization, PricingPlan, Site, User

logger = logging.getLogger("sentinel.api")


def bootstrap_admin() -> None:
    if len(settings.bootstrap_admin_password) < 8:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD must be at least 8 characters")
    db = SessionLocal()
    try:
        existing = db.scalar(select(func.count()).select_from(User))
        if existing:
            return
        organization = Organization(name=settings.bootstrap_org_name.strip(), timezone=DEFAULT_TIMEZONE)
        db.add(organization)
        db.flush()
        db.add(
            User(
                organization_id=organization.id,
                email=settings.bootstrap_admin_email.strip().lower(),
                password_hash=hash_password(settings.bootstrap_admin_password),
                full_name=settings.bootstrap_admin_name.strip(),
                role="admin",
            )
        )
        db.add(
            PricingPlan(
                organization_id=organization.id,
                currency="GTQ",
                rate_per_minute=Decimal("0"),
                setup_fee=Decimal("0"),
            )
        )
        db.commit()
        logger.info("bootstrap admin created for organization %s", organization.id)
    finally:
        db.close()


def ensure_bootstrap_device() -> None:
    token = settings.bootstrap_device_token
    if not token:
        return
    digest = hash_device_token(token)
    db = SessionLocal()
    try:
        existing = db.scalar(select(Device.id).where(Device.token_hash == digest))
        if existing:
            return
        site = db.scalar(select(Site).order_by(Site.created_at.asc()).limit(1))
        if site is None:
            logger.info("bootstrap device waiting for the first site")
            return
        db.add(
            Device(
                organization_id=site.organization_id,
                site_id=site.id,
                name="Dispositivo demo",
                token_hash=digest,
            )
        )
        db.commit()
        logger.info("bootstrap device created for site %s", site.id)
    finally:
        db.close()
