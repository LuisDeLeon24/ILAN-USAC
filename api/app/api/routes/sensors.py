import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, scoped_get
from app.db.session import get_db
from app.models.entities import Sensor, Site, User
from app.schemas.sensors import SensorRead, SensorWrite

router = APIRouter(prefix="/sensors", tags=["sensors"])
logger = logging.getLogger("sentinel.api")


def _read(sensor: Sensor) -> SensorRead:
    return SensorRead(
        id=sensor.id,
        site_id=sensor.site_id,
        name=sensor.name,
        sensor_type=sensor.sensor_type,  # type: ignore[arg-type]
        external_id=sensor.external_id,
        created_at=sensor.created_at,
    )


def _taken(db: Session, user: User, external_id: str, ignore_id: uuid.UUID | None = None) -> bool:
    existing = db.scalar(
        select(Sensor).where(Sensor.organization_id == user.organization_id, Sensor.external_id == external_id)
    )
    return existing is not None and existing.id != ignore_id


@router.get("", response_model=list[SensorRead])
def list_sensors(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> list[SensorRead]:
    rows = db.scalars(
        select(Sensor).where(Sensor.organization_id == user.organization_id).order_by(Sensor.created_at.desc()).limit(200)
    )
    return [_read(sensor) for sensor in rows]


@router.post("", response_model=SensorRead, status_code=201)
def create_sensor(
    payload: SensorWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SensorRead:
    scoped_get(db, Site, user, payload.site_id)
    if _taken(db, user, payload.external_id):
        raise HTTPException(status_code=409, detail="Ya existe un sensor con ese identificador")
    sensor = Sensor(
        organization_id=user.organization_id,
        site_id=payload.site_id,
        name=payload.name,
        sensor_type=payload.sensor_type,
        external_id=payload.external_id,
    )
    db.add(sensor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un sensor con ese identificador") from None
    db.refresh(sensor)
    logger.info("sensor created org=%s sensor=%s type=%s", user.organization_id, sensor.id, sensor.sensor_type)
    return _read(sensor)


@router.patch("/{sensor_id}", response_model=SensorRead)
def update_sensor(
    sensor_id: uuid.UUID,
    payload: SensorWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> SensorRead:
    sensor = scoped_get(db, Sensor, user, sensor_id)
    scoped_get(db, Site, user, payload.site_id)
    if _taken(db, user, payload.external_id, ignore_id=sensor.id):
        raise HTTPException(status_code=409, detail="Ya existe un sensor con ese identificador")
    sensor.site_id = payload.site_id
    sensor.name = payload.name
    sensor.sensor_type = payload.sensor_type
    sensor.external_id = payload.external_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un sensor con ese identificador") from None
    db.refresh(sensor)
    return _read(sensor)


@router.delete("/{sensor_id}", status_code=204)
def delete_sensor(
    sensor_id: uuid.UUID,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    sensor = scoped_get(db, Sensor, user, sensor_id)
    db.delete(sensor)
    db.commit()
    logger.info("sensor deleted org=%s sensor=%s", user.organization_id, sensor_id)
    return Response(status_code=204)
