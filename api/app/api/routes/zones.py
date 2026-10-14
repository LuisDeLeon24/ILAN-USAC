import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, scoped_get
from app.db.session import get_db
from app.models.entities import Camera, User, Zone
from app.schemas.zones import ZoneRead, ZoneWrite

router = APIRouter(tags=["zones"])
logger = logging.getLogger("sentinel.api")


def to_read(zone: Zone) -> ZoneRead:
    return ZoneRead(
        id=zone.id,
        camera_id=zone.camera_id,
        name=zone.name,
        polygon=zone.polygon,
        schedule=zone.schedule,
        rule_type=zone.rule_type,  # type: ignore[arg-type]
        rule_params=zone.rule_params,
        created_at=zone.created_at,
    )


@router.get("/cameras/{camera_id}/zones", response_model=list[ZoneRead])
def list_zones(
    camera_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ZoneRead]:
    scoped_get(db, Camera, user, camera_id)
    zones = db.scalars(
        select(Zone)
        .where(Zone.camera_id == camera_id, Zone.organization_id == user.organization_id)
        .order_by(Zone.created_at.desc())
        .limit(200)
    )
    return [to_read(zone) for zone in zones]


@router.post("/cameras/{camera_id}/zones", response_model=ZoneRead, status_code=201)
def create_zone(
    camera_id: uuid.UUID,
    payload: ZoneWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ZoneRead:
    scoped_get(db, Camera, user, camera_id)
    zone = Zone(
        organization_id=user.organization_id,
        camera_id=camera_id,
        name=payload.name,
        polygon=payload.polygon,
        schedule=payload.schedule.model_dump(),
        rule_type=payload.rule_type,
        rule_params=payload.rule_params,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    logger.info("zone created org=%s zone=%s rule=%s", user.organization_id, zone.id, zone.rule_type)
    return to_read(zone)


@router.patch("/zones/{zone_id}", response_model=ZoneRead)
def update_zone(
    zone_id: uuid.UUID,
    payload: ZoneWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ZoneRead:
    zone = scoped_get(db, Zone, user, zone_id)
    zone.name = payload.name
    zone.polygon = payload.polygon
    zone.schedule = payload.schedule.model_dump()
    zone.rule_type = payload.rule_type
    zone.rule_params = payload.rule_params
    db.commit()
    db.refresh(zone)
    return to_read(zone)


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(
    zone_id: uuid.UUID,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    zone = scoped_get(db, Zone, user, zone_id)
    db.delete(zone)
    db.commit()
    logger.info("zone deleted org=%s zone=%s", user.organization_id, zone_id)
    return Response(status_code=204)
