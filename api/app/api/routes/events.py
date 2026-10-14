import logging
import uuid
from datetime import date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, scoped_get
from app.core.config import DEFAULT_TIMEZONE
from app.db.session import get_db
from app.models.entities import Camera, Event, Sensor, User
from app.schemas.events import EventRead, EventStatusWrite
from app.services.event_status import apply_event_status
from app.services.storage import get_bytes

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger("sentinel.api")
LIST_LIMIT = 200
GUATEMALA = ZoneInfo(DEFAULT_TIMEZONE)
EVENT_TYPES = {
    "intrusion",
    "after_hours",
    "loitering",
    "occupancy",
    "camera_disconnected",
    "door_open",
    "motion",
    "smoke",
    "panic",
}
SEVERITIES = {"low", "medium", "high", "critical"}


def _window(start: date | None, end: date | None) -> tuple[datetime, datetime]:
    today = datetime.now(GUATEMALA).date()
    if start is None and end is None:
        start = today - timedelta(days=6)
        end = today
    elif start is None or end is None:
        raise HTTPException(status_code=422, detail="Indica el inicio y el fin del periodo")
    if start > end:
        raise HTTPException(status_code=422, detail="La fecha de inicio debe ser anterior o igual a la de fin")
    start_at = datetime.combine(start, time.min, tzinfo=GUATEMALA)
    end_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=GUATEMALA)
    return start_at, end_at


def _read(event: Event, camera_name: str | None, sensor_name: str | None = None) -> EventRead:
    return EventRead(
        id=event.id,
        event_type=event.event_type,
        severity=event.severity,  # type: ignore[arg-type]
        status=event.status,  # type: ignore[arg-type]
        camera_id=event.camera_id,
        camera_name=camera_name,
        sensor_id=event.sensor_id,
        sensor_name=sensor_name,
        occurred_at=event.occurred_at,
        reviewed_at=event.reviewed_at,
        has_snapshot=bool(event.snapshot_key),
    )


def _sensor_name(db: Session, event: Event) -> str | None:
    if event.sensor_id is None:
        return None
    sensor = db.get(Sensor, event.sensor_id)
    if sensor is None or sensor.organization_id != event.organization_id:
        return None
    return sensor.name


@router.get("", response_model=list[EventRead])
def list_events(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    start: date | None = None,
    end: date | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    camera_id: uuid.UUID | None = None,
) -> list[EventRead]:
    if event_type is not None and event_type not in EVENT_TYPES:
        raise HTTPException(status_code=422, detail="Tipo de evento no válido")
    if severity is not None and severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail="Severidad no válida")
    if camera_id is not None:
        scoped_get(db, Camera, user, camera_id)
    start_at, end_at = _window(start, end)
    query = (
        select(Event, Camera.name, Sensor.name)
        .outerjoin(Camera, Camera.id == Event.camera_id)
        .outerjoin(Sensor, Sensor.id == Event.sensor_id)
        .where(
            Event.organization_id == user.organization_id,
            Event.occurred_at >= start_at,
            Event.occurred_at < end_at,
        )
    )
    if event_type is not None:
        query = query.where(Event.event_type == event_type)
    if severity is not None:
        query = query.where(Event.severity == severity)
    if camera_id is not None:
        query = query.where(Event.camera_id == camera_id)
    rows = db.execute(query.order_by(Event.occurred_at.desc()).limit(LIST_LIMIT)).all()
    return [_read(event, camera_name, sensor_name) for event, camera_name, sensor_name in rows]


@router.patch("/{event_id}", response_model=EventRead)
def update_event_status(
    event_id: uuid.UUID,
    payload: EventStatusWrite,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EventRead:
    event = scoped_get(db, Event, user, event_id)
    apply_event_status(event, payload.status)
    db.commit()
    db.refresh(event)
    camera_name = None
    if event.camera_id is not None:
        camera = db.get(Camera, event.camera_id)
        if camera is not None and camera.organization_id == user.organization_id:
            camera_name = camera.name
    logger.info("event status org=%s event=%s status=%s", user.organization_id, event.id, payload.status)
    return _read(event, camera_name, _sensor_name(db, event))


@router.get("/{event_id}/snapshot")
def event_snapshot(
    event_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    event = scoped_get(db, Event, user, event_id)
    if not event.snapshot_key:
        raise HTTPException(status_code=404, detail="No encontrado")
    return Response(content=get_bytes(event.snapshot_key), media_type="image/jpeg")
