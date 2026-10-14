import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, scoped_get
from app.db.session import get_db
from app.models.entities import Camera, Site, User
from app.services.bootstrap import ensure_bootstrap_device
from app.schemas.sites import SiteCreate, SiteRead, SiteUpdate

router = APIRouter(prefix="/sites", tags=["sites"])
logger = logging.getLogger("sentinel.api")


def _reads(db: Session, user: User) -> list[SiteRead]:
    rows = db.execute(
        select(Site, func.count(Camera.id))
        .outerjoin(Camera, Camera.site_id == Site.id)
        .where(Site.organization_id == user.organization_id)
        .group_by(Site.id)
        .order_by(Site.created_at.desc())
        .limit(200)
    ).all()
    return [
        SiteRead(id=site.id, name=site.name, address=site.address, camera_count=count, created_at=site.created_at)
        for site, count in rows
    ]


@router.get("", response_model=list[SiteRead])
def list_sites(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> list[SiteRead]:
    return _reads(db, user)


@router.post("", response_model=SiteRead, status_code=201)
def create_site(
    payload: SiteCreate,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SiteRead:
    site = Site(organization_id=user.organization_id, name=payload.name, address=payload.address)
    db.add(site)
    db.commit()
    db.refresh(site)
    logger.info("site created org=%s site=%s", user.organization_id, site.id)
    ensure_bootstrap_device()
    return SiteRead(id=site.id, name=site.name, address=site.address, camera_count=0, created_at=site.created_at)


@router.patch("/{site_id}", response_model=SiteRead)
def update_site(
    site_id: uuid.UUID,
    payload: SiteUpdate,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SiteRead:
    site = scoped_get(db, Site, user, site_id)
    site.name = payload.name
    site.address = payload.address
    db.commit()
    db.refresh(site)
    count = db.scalar(select(func.count()).select_from(Camera).where(Camera.site_id == site.id)) or 0
    return SiteRead(id=site.id, name=site.name, address=site.address, camera_count=count, created_at=site.created_at)


@router.delete("/{site_id}", status_code=204)
def delete_site(
    site_id: uuid.UUID,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    site = scoped_get(db, Site, user, site_id)
    cameras = db.scalar(select(func.count()).select_from(Camera).where(Camera.site_id == site.id)) or 0
    if cameras:
        raise HTTPException(status_code=409, detail="Elimina las cámaras de este sitio antes de eliminarlo")
    db.delete(site)
    db.commit()
    logger.info("site deleted org=%s site=%s", user.organization_id, site_id)
    ensure_bootstrap_device()
    return Response(status_code=204)
