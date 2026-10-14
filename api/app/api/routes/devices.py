import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_device
from app.core.config import DEFAULT_TIMEZONE, settings
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.entities import Camera, Device, Event, ExclusionArea, Organization, Sensor, UsageRecord, UsageReport, Zone
from app.schemas.device import (
    SEVERITY_FOR_TYPE,
    CameraConfig,
    DeviceConfig,
    DeviceEventResult,
    DeviceEventWrite,
    DeviceFrameResult,
    DeviceSensorEventWrite,
    DeviceUsageResult,
    DeviceUsageWrite,
    ExclusionConfig,
    HeartbeatWrite,
    SensorConfig,
    ZoneConfig,
)
from app.schemas.sensors import SENSOR_EVENTS
from app.services.alerts import dispatch_event_alerts
from app.services.storage import put_bytes

router = APIRouter(prefix="/device", tags=["device"])
logger = logging.getLogger("sentinel.api")
MAX_SNAPSHOT_BYTES = 2_000_000


def _camera_for_device(db: Session, device: Device, camera_id: uuid.UUID) -> Camera:
    camera = db.scalar(
        select(Camera).where(
            Camera.id == camera_id,
            Camera.organization_id == device.organization_id,
            Camera.site_id == device.site_id,
        )
    )
    if camera is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return camera


@router.post("/heartbeat")
def heartbeat(
    payload: HeartbeatWrite,
    device: Annotated[Device, Depends(get_device)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, bool]:
    device.last_seen_at = datetime.now(timezone.utc)
    device.model_version = payload.model_version
    db.commit()
    logger.info("heartbeat device=%s model=%s", device.id, payload.model_version)
    return {"ok": True}


@router.get("/config", response_model=DeviceConfig)
def device_config(device: Annotated[Device, Depends(get_device)], db: Annotated[Session, Depends(get_db)]) -> DeviceConfig:
    organization = db.get(Organization, device.organization_id)
    cameras = list(
        db.scalars(
            select(Camera)
            .where(
                Camera.organization_id == device.organization_id,
                Camera.site_id == device.site_id,
                Camera.enabled.is_(True),
            )
            .order_by(Camera.created_at.asc())
        )
    )
    zones_by_camera: dict[uuid.UUID, list[Zone]] = {camera.id: [] for camera in cameras}
    exclusions_by_camera: dict[uuid.UUID, list[ExclusionArea]] = {camera.id: [] for camera in cameras}
    if cameras:
        camera_ids = [camera.id for camera in cameras]
        zones = db.scalars(
            select(Zone).where(
                Zone.organization_id == device.organization_id,
                Zone.camera_id.in_(camera_ids),
            )
        )
        for zone in zones:
            zones_by_camera.setdefault(zone.camera_id, []).append(zone)
        exclusions = db.scalars(
            select(ExclusionArea).where(
                ExclusionArea.organization_id == device.organization_id,
                ExclusionArea.camera_id.in_(camera_ids),
            )
        )
        for area in exclusions:
            exclusions_by_camera.setdefault(area.camera_id, []).append(area)
    configured: list[CameraConfig] = []
    for camera in cameras:
        rtsp_url = None
        if camera.source_type == "rtsp" and camera.rtsp_url_encrypted:
            try:
                rtsp_url = decrypt_secret(camera.rtsp_url_encrypted)
            except Exception:
                logger.exception("failed to decrypt rtsp url for camera %s", camera.id)
        configured.append(
            CameraConfig(
                id=camera.id,
                name=camera.name,
                source_type=camera.source_type,  # type: ignore[arg-type]
                file_path=camera.file_path,
                rtsp_url=rtsp_url,
                fps=camera.fps,
                loop=camera.loop,
                min_confidence=float(camera.min_confidence),
                min_box_area=float(camera.min_box_area),
                frame_requested=camera.frame_requested,
                zones=[
                    ZoneConfig(
                        id=zone.id,
                        name=zone.name,
                        polygon=zone.polygon,
                        schedule=zone.schedule,
                        rule_type=zone.rule_type,
                        rule_params=zone.rule_params,
                    )
                    for zone in zones_by_camera.get(camera.id, [])
                ],
                exclusions=[
                    ExclusionConfig(id=area.id, polygon=area.polygon)
                    for area in exclusions_by_camera.get(camera.id, [])
                ],
            )
        )
    sensors = list(
        db.scalars(
            select(Sensor)
            .where(Sensor.organization_id == device.organization_id, Sensor.site_id == device.site_id)
            .order_by(Sensor.created_at.asc())
        )
    )
    return DeviceConfig(
        device_id=device.id,
        site_id=device.site_id,
        organization_id=device.organization_id,
        timezone=organization.timezone if organization else DEFAULT_TIMEZONE,
        cooldown_seconds=settings.event_cooldown_seconds,
        cameras=configured,
        sensors=[
            SensorConfig(id=sensor.id, name=sensor.name, sensor_type=sensor.sensor_type, external_id=sensor.external_id)
            for sensor in sensors
        ],
    )


def _existing_event(db: Session, client_event_id: str) -> Event | None:
    return db.scalar(select(Event).where(Event.client_event_id == client_event_id))


@router.post("/events", response_model=DeviceEventResult)
def ingest_event(
    device: Annotated[Device, Depends(get_device)],
    db: Annotated[Session, Depends(get_db)],
    background: BackgroundTasks,
    meta: Annotated[str, Form()],
    snapshot: Annotated[UploadFile | None, File()] = None,
) -> DeviceEventResult:
    try:
        payload = DeviceEventWrite.model_validate_json(meta)
    except ValidationError as exc:
        message = "Datos inválidos"
        errors = exc.errors()
        if errors:
            detail = str(errors[0].get("msg", ""))
            if detail.startswith("Value error, "):
                message = detail.removeprefix("Value error, ")
        raise HTTPException(status_code=422, detail=message) from None
    camera = _camera_for_device(db, device, payload.camera_id)
    zone_id = payload.zone_id
    if payload.event_type == "camera_disconnected":
        zone_id = None
        cooldown_key = f"{camera.id}:disconnected"
    else:
        if zone_id is None:
            raise HTTPException(status_code=422, detail="La zona es obligatoria")
        zone = db.scalar(
            select(Zone).where(
                Zone.id == zone_id,
                Zone.camera_id == camera.id,
                Zone.organization_id == device.organization_id,
            )
        )
        if zone is None:
            raise HTTPException(status_code=404, detail="No encontrado")
        cooldown_key = f"{camera.id}:{zone.id}:{payload.event_type}"
    existing = _existing_event(db, payload.client_event_id)
    if existing is not None:
        if existing.organization_id != device.organization_id:
            raise HTTPException(status_code=409, detail="El evento ya existe")
        return DeviceEventResult(id=existing.id, created=False)
    since = payload.occurred_at - timedelta(seconds=settings.event_cooldown_seconds)
    previous = db.scalar(
        select(Event)
        .where(
            Event.organization_id == device.organization_id,
            Event.cooldown_key == cooldown_key,
            Event.occurred_at >= since,
        )
        .order_by(Event.occurred_at.desc())
    )
    if previous is not None:
        return DeviceEventResult(id=previous.id, created=False)
    image = b""
    if snapshot is not None:
        image = snapshot.file.read(MAX_SNAPSHOT_BYTES + 1)
        if len(image) > MAX_SNAPSHOT_BYTES:
            raise HTTPException(status_code=422, detail="La imagen es demasiado grande")
        if image and image[:2] != b"\xff\xd8":
            raise HTTPException(status_code=422, detail="La imagen debe ser JPG")
    event = Event(
        id=uuid.uuid4(),
        organization_id=device.organization_id,
        camera_id=camera.id,
        zone_id=zone_id,
        event_type=payload.event_type,
        severity=SEVERITY_FOR_TYPE[payload.event_type],
        status="new",
        occurred_at=payload.occurred_at,
        cooldown_key=cooldown_key,
        client_event_id=payload.client_event_id,
    )
    if image:
        event.snapshot_key = f"{device.organization_id}/{event.id}.jpg"
        put_bytes(event.snapshot_key, image, "image/jpeg")
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = _existing_event(db, payload.client_event_id)
        if raced is None or raced.organization_id != device.organization_id:
            raise HTTPException(status_code=409, detail="El evento ya existe") from None
        return DeviceEventResult(id=raced.id, created=False)
    logger.info("event created org=%s camera=%s type=%s", device.organization_id, camera.id, payload.event_type)
    background.add_task(dispatch_event_alerts, event.id)
    return DeviceEventResult(id=event.id, created=True)


@router.post("/sensor-events", response_model=DeviceEventResult)
def ingest_sensor_event(
    payload: DeviceSensorEventWrite,
    device: Annotated[Device, Depends(get_device)],
    db: Annotated[Session, Depends(get_db)],
    background: BackgroundTasks,
) -> DeviceEventResult:
    sensor = db.scalar(
        select(Sensor).where(
            Sensor.id == payload.sensor_id,
            Sensor.organization_id == device.organization_id,
            Sensor.site_id == device.site_id,
        )
    )
    if sensor is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    expected, severity = SENSOR_EVENTS[sensor.sensor_type]
    if payload.event_type != expected:
        raise HTTPException(status_code=422, detail="El tipo de evento no corresponde al sensor")
    cooldown_key = f"sensor:{sensor.id}:{payload.event_type}"
    existing = _existing_event(db, payload.client_event_id)
    if existing is not None:
        if existing.organization_id != device.organization_id:
            raise HTTPException(status_code=409, detail="El evento ya existe")
        return DeviceEventResult(id=existing.id, created=False)
    since = payload.occurred_at - timedelta(seconds=settings.event_cooldown_seconds)
    previous = db.scalar(
        select(Event)
        .where(
            Event.organization_id == device.organization_id,
            Event.cooldown_key == cooldown_key,
            Event.occurred_at >= since,
        )
        .order_by(Event.occurred_at.desc())
    )
    if previous is not None:
        return DeviceEventResult(id=previous.id, created=False)
    event = Event(
        id=uuid.uuid4(),
        organization_id=device.organization_id,
        sensor_id=sensor.id,
        event_type=payload.event_type,
        severity=severity,
        status="new",
        occurred_at=payload.occurred_at,
        cooldown_key=cooldown_key,
        client_event_id=payload.client_event_id,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = _existing_event(db, payload.client_event_id)
        if raced is None or raced.organization_id != device.organization_id:
            raise HTTPException(status_code=409, detail="El evento ya existe") from None
        return DeviceEventResult(id=raced.id, created=False)
    logger.info("sensor event created org=%s sensor=%s type=%s", device.organization_id, sensor.id, payload.event_type)
    background.add_task(dispatch_event_alerts, event.id)
    return DeviceEventResult(id=event.id, created=True)


@router.post("/usage", response_model=DeviceUsageResult)
def ingest_usage(
    payload: DeviceUsageWrite,
    device: Annotated[Device, Depends(get_device)],
    db: Annotated[Session, Depends(get_db)],
) -> DeviceUsageResult:
    camera = _camera_for_device(db, device, payload.camera_id)
    amount = Decimal(str(payload.analyzed_minutes)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Los minutos analizados no son válidos")
    existing = db.scalar(select(UsageReport).where(UsageReport.client_report_id == payload.client_report_id))
    if existing is not None:
        if existing.organization_id != device.organization_id:
            raise HTTPException(status_code=409, detail="El reporte ya existe")
        return DeviceUsageResult(analyzed_minutes=float(existing.analyzed_minutes), created=False)
    report = UsageReport(
        organization_id=device.organization_id,
        camera_id=camera.id,
        client_report_id=payload.client_report_id,
        usage_date=payload.usage_date,
        analyzed_minutes=amount,
    )
    record = db.scalar(
        select(UsageRecord).where(UsageRecord.camera_id == camera.id, UsageRecord.usage_date == payload.usage_date)
    )
    if record is None:
        record = UsageRecord(
            organization_id=device.organization_id,
            camera_id=camera.id,
            usage_date=payload.usage_date,
            analyzed_minutes=amount,
        )
        db.add(record)
    else:
        record.analyzed_minutes = Decimal(record.analyzed_minutes) + amount
    db.add(report)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raced = db.scalar(select(UsageReport).where(UsageReport.client_report_id == payload.client_report_id))
        if raced is None or raced.organization_id != device.organization_id:
            raise HTTPException(status_code=409, detail="El reporte ya existe") from None
        return DeviceUsageResult(analyzed_minutes=float(raced.analyzed_minutes), created=False)
    logger.info("usage recorded org=%s camera=%s minutes=%s", device.organization_id, camera.id, amount)
    return DeviceUsageResult(analyzed_minutes=float(amount), created=True)


@router.post("/frames", response_model=DeviceFrameResult)
def ingest_frame(
    device: Annotated[Device, Depends(get_device)],
    db: Annotated[Session, Depends(get_db)],
    camera_id: Annotated[uuid.UUID, Form()],
    frame: Annotated[UploadFile, File()],
) -> DeviceFrameResult:
    camera = _camera_for_device(db, device, camera_id)
    if not camera.frame_requested:
        raise HTTPException(status_code=409, detail="No hay una solicitud de cuadro")
    image = frame.file.read(MAX_SNAPSHOT_BYTES + 1)
    if len(image) > MAX_SNAPSHOT_BYTES:
        raise HTTPException(status_code=422, detail="La imagen es demasiado grande")
    if not image or image[:2] != b"\xff\xd8":
        raise HTTPException(status_code=422, detail="La imagen debe ser JPG")
    camera.preview_key = f"frames/{device.organization_id}/{camera.id}.jpg"
    put_bytes(camera.preview_key, image, "image/jpeg")
    camera.preview_at = datetime.now(timezone.utc)
    camera.frame_requested = False
    db.commit()
    logger.info("frame stored org=%s camera=%s", device.organization_id, camera.id)
    return DeviceFrameResult(received=True)
