"""Curated demo organization. The CLI in app.seed is the only entry that wipes data."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TIMEZONE
from app.core.security import hash_device_token, hash_password
from app.models.entities import (
    AgentConversation,
    AgentMessage,
    AgentToolCall,
    AlertContact,
    AlertLog,
    Camera,
    Device,
    Event,
    ExclusionArea,
    Organization,
    PricingPlan,
    Sensor,
    Site,
    UsageRecord,
    UsageReport,
    User,
    Zone,
)
from app.services.agent.dates import GUATEMALA
from app.services.storage import put_bytes

DEMO_ADMIN_NAME = "Elena Morales"
DEMO_RATE = Decimal("0.005")
DEMO_PHONE = "+50200000000"
DAILY_MINUTES = {
    "Acceso norte": Decimal("1440"),
    "Patio de carga": Decimal("840"),
    "Andén bodega": Decimal("720"),
}
MIN_FRAMES = 6
WEEK_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

SEVERITY = {
    "intrusion": "high",
    "after_hours": "high",
    "loitering": "medium",
    "occupancy": "medium",
    "camera_disconnected": "high",
    "door_open": "medium",
    "motion": "low",
    "smoke": "critical",
}

WIPE_ORDER = (
    (AgentToolCall, "llamada del asistente", "llamadas del asistente"),
    (AgentMessage, "mensaje del asistente", "mensajes del asistente"),
    (AgentConversation, "conversación", "conversaciones"),
    (AlertLog, "intento de alerta", "intentos de alerta"),
    (AlertContact, "contacto de alerta", "contactos de alerta"),
    (UsageReport, "reporte de uso", "reportes de uso"),
    (UsageRecord, "registro de minutos", "registros de minutos"),
    (Event, "evento", "eventos"),
    (Sensor, "sensor", "sensores"),
    (Zone, "zona", "zonas"),
    (ExclusionArea, "exclusión", "exclusiones"),
    (Camera, "cámara", "cámaras"),
    (Device, "dispositivo", "dispositivos"),
    (Site, "sitio", "sitios"),
    (PricingPlan, "tarifa", "tarifas"),
    (User, "usuario", "usuarios"),
    (Organization, "organización", "organizaciones"),
)


@dataclass(frozen=True)
class SeedEvent:
    day_offset: int
    hour: int
    minute: int
    source: str
    event_type: str
    status: str
    review_minutes: int | None = None


@dataclass(frozen=True)
class PlannedEvent:
    occurred_at: datetime
    source: str
    event_type: str
    severity: str
    status: str
    reviewed_at: datetime | None
    snapshot: bool


@dataclass(frozen=True)
class DemoResult:
    organization_id: uuid.UUID
    organization_name: str
    email: str
    full_name: str
    events: int
    snapshots: int


# day_offset is relative to the seed day in America/Guatemala.
# Cameras stay disabled so the worker does not append live events on top of this week.
EVENTS: tuple[SeedEvent, ...] = (
    SeedEvent(-6, 9, 15, "acceso", "intrusion", "resolved", 8),
    SeedEvent(-5, 11, 40, "acceso", "intrusion", "new"),
    SeedEvent(-3, 8, 12, "acceso", "intrusion", "in_review", 6),
    SeedEvent(-2, 14, 20, "acceso", "intrusion", "resolved", 11),
    SeedEvent(-1, 9, 5, "acceso", "intrusion", "new"),
    SeedEvent(0, 8, 20, "acceso", "intrusion", "in_review", 7),
    SeedEvent(0, 10, 40, "acceso", "intrusion", "new"),
    SeedEvent(0, 17, 15, "acceso", "intrusion", "false_positive"),
    SeedEvent(-5, 22, 10, "anden", "after_hours", "new"),
    SeedEvent(-4, 23, 5, "anden", "after_hours", "resolved", 15),
    SeedEvent(-3, 1, 20, "anden", "after_hours", "in_review", 20),
    SeedEvent(-1, 2, 40, "anden", "after_hours", "new"),
    SeedEvent(-6, 16, 0, "patio", "loitering", "new"),
    SeedEvent(-2, 15, 30, "patio", "loitering", "resolved", 9),
    SeedEvent(-1, 11, 25, "patio", "loitering", "in_review", 5),
    SeedEvent(0, 12, 5, "patio", "loitering", "new"),
    SeedEvent(-5, 10, 0, "patio", "occupancy", "in_review", 4),
    SeedEvent(-3, 9, 50, "patio", "occupancy", "resolved", 10),
    SeedEvent(-1, 17, 45, "patio", "occupancy", "new"),
    SeedEvent(0, 15, 0, "patio", "occupancy", "resolved", 8),
    SeedEvent(-2, 3, 0, "acceso", "camera_disconnected", "new"),
    SeedEvent(-6, 7, 30, "puerta", "door_open", "new"),
    SeedEvent(-5, 13, 40, "puerta", "door_open", "resolved", 6),
    SeedEvent(-4, 8, 0, "puerta", "door_open", "in_review", 3),
    SeedEvent(-3, 18, 20, "puerta", "door_open", "new"),
    SeedEvent(-2, 12, 0, "puerta", "door_open", "resolved", 14),
    SeedEvent(-1, 7, 50, "puerta", "door_open", "new"),
    SeedEvent(0, 9, 10, "puerta", "door_open", "false_positive"),
    SeedEvent(-6, 20, 0, "movimiento", "motion", "new"),
    SeedEvent(-5, 21, 10, "movimiento", "motion", "resolved", 30),
    SeedEvent(-4, 19, 0, "movimiento", "motion", "new"),
    SeedEvent(-3, 6, 10, "movimiento", "motion", "in_review", 12),
    SeedEvent(-2, 22, 30, "movimiento", "motion", "new"),
    SeedEvent(-1, 20, 15, "movimiento", "motion", "false_positive"),
    SeedEvent(0, 19, 40, "movimiento", "motion", "new"),
    SeedEvent(-5, 5, 0, "humo", "smoke", "resolved", 2),
    SeedEvent(-1, 4, 12, "humo", "smoke", "new"),
)


def _schedule(start: str, end: str) -> dict:
    return {
        "timezone": DEFAULT_TIMEZONE,
        "windows": [{"days": list(WEEK_DAYS), "start": start, "end": end}],
    }


def needs_snapshot(event: SeedEvent) -> bool:
    return event.source in {"acceso", "patio", "anden"} and event.event_type != "camera_disconnected"


def deletion_lines(db: Session) -> list[str]:
    lines: list[str] = []
    for model, singular, plural in WIPE_ORDER:
        count = int(db.scalar(select(func.count()).select_from(model)) or 0)
        if count:
            lines.append(f"{count} {singular if count == 1 else plural}")
    return lines


def wipe_all(db: Session) -> None:
    for model, _singular, _plural in WIPE_ORDER:
        db.execute(delete(model))
    db.flush()


def planned_events(moment: datetime) -> list[PlannedEvent]:
    local = moment.astimezone(GUATEMALA)
    planned: list[PlannedEvent] = []
    for event in EVENTS:
        day = local.date() + timedelta(days=event.day_offset)
        occurred = datetime.combine(day, time(event.hour, event.minute), tzinfo=GUATEMALA)
        reviewed = None
        if event.status in {"in_review", "resolved"}:
            reviewed = occurred + timedelta(minutes=event.review_minutes or 5)
        planned.append(
            PlannedEvent(
                occurred_at=occurred,
                source=event.source,
                event_type=event.event_type,
                severity=SEVERITY[event.event_type],
                status=event.status,
                reviewed_at=reviewed,
                snapshot=needs_snapshot(event),
            )
        )
    return planned


def usage_dates(moment: datetime) -> list[date]:
    """Days that should carry analyzed minutes.

    The open month is filled from the 1st through today. On the 1st, 2nd, or 3rd
    the previous month is included so the metrics page has a full month beside
    the short month-to-date total. Event history is separate and stays at one week.
    """
    local = moment.astimezone(GUATEMALA).date()
    month_start = local.replace(day=1)
    dates: list[date] = []
    if local.day <= 3:
        previous = month_start - timedelta(days=1)
        cursor = previous.replace(day=1)
        while cursor < month_start:
            dates.append(cursor)
            cursor += timedelta(days=1)
    cursor = month_start
    while cursor <= local:
        dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def minutes_for(camera_name: str, day: date) -> Decimal:
    """Base shift length, moved by at most 5% in a way that repeats for the same day."""
    base = DAILY_MINUTES[camera_name]
    slot = sum(ord(char) for char in f"{camera_name}|{day.isoformat()}") % 101
    delta = Decimal(slot - 50) / Decimal(1000)
    return (base * (Decimal(1) + delta)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def minutes_on(days: list[date]) -> Decimal:
    total = Decimal(0)
    for day in days:
        for camera_name in DAILY_MINUTES:
            total += minutes_for(camera_name, day)
    return total


def insert_demo(
    db: Session,
    frames: list[bytes],
    *,
    email: str,
    password: str,
    organization_name: str,
    full_name: str = DEMO_ADMIN_NAME,
    device_token: str | None = None,
    moment: datetime | None = None,
    upload: Callable[[str, bytes], None] | None = None,
    id_prefix: str = "demo",
) -> DemoResult:
    if len(frames) < MIN_FRAMES:
        raise ValueError(f"Se necesitan al menos {MIN_FRAMES} cuadros anotados")
    store = upload or (lambda key, payload: put_bytes(key, payload, "image/jpeg"))
    when = (moment or datetime.now(GUATEMALA)).astimezone(GUATEMALA)
    name = organization_name.strip()
    if not name:
        raise ValueError("El nombre de la organización está vacío")
    organization = Organization(name=name, timezone=DEFAULT_TIMEZONE)
    db.add(organization)
    db.flush()
    db.add(
        User(
            organization_id=organization.id,
            email=email.strip().lower(),
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            role="admin",
        )
    )
    db.add(
        PricingPlan(
            organization_id=organization.id,
            currency="GTQ",
            rate_per_minute=DEMO_RATE,
            setup_fee=Decimal("0"),
        )
    )
    planta = Site(organization_id=organization.id, name="Planta norte", address="Carretera al Atlántico, km 12")
    bodega = Site(organization_id=organization.id, name="Bodega central", address="Zona 12, Ciudad de Guatemala")
    db.add_all([planta, bodega])
    db.flush()
    cameras = {
        "acceso": _camera(organization.id, planta.id, "Acceso norte"),
        "patio": _camera(organization.id, planta.id, "Patio de carga"),
        "anden": _camera(organization.id, bodega.id, "Andén bodega"),
    }
    db.add_all(cameras.values())
    db.flush()
    zones = {
        ("acceso", "intrusion"): _zone(organization.id, cameras["acceso"].id, "Acceso restringido", "intrusion", {}),
        ("patio", "loitering"): _zone(
            organization.id, cameras["patio"].id, "Patio", "loitering", {"seconds": 45}, "06:00", "18:00"
        ),
        ("patio", "occupancy"): _zone(
            organization.id,
            cameras["patio"].id,
            "Muelle",
            "occupancy",
            {"max_people": 4},
            "06:00",
            "18:00",
            [[0.4, 0.4], [0.95, 0.35], [0.98, 0.92], [0.45, 0.95]],
        ),
        ("anden", "after_hours"): _zone(
            organization.id,
            cameras["anden"].id,
            "Andén",
            "after_hours",
            {},
            "07:00",
            "18:00",
            [[0.2, 0.15], [0.8, 0.15], [0.85, 0.8], [0.15, 0.85]],
        ),
    }
    db.add_all(zones.values())
    # Live door and smoke readings arrive through the demo edge device, which only
    # serves Planta norte. Both sensors stay on that site so the simulator can create events.
    sensors = {
        "puerta": _sensor(organization.id, planta.id, "Puerta norte", "door", "puerta-norte"),
        "movimiento": _sensor(organization.id, planta.id, "Movimiento patio", "motion", "movimiento-patio"),
        "humo": _sensor(organization.id, planta.id, "Detector de humo", "smoke", "humo-planta"),
    }
    db.add_all(sensors.values())
    db.add(
        AlertContact(
            organization_id=organization.id,
            name="Central de monitoreo",
            channel="whatsapp",
            phone=DEMO_PHONE,
            enabled=False,
        )
    )
    if device_token:
        db.add(
            Device(
                organization_id=organization.id,
                site_id=planta.id,
                name="Dispositivo demo",
                token_hash=hash_device_token(device_token),
            )
        )
    db.flush()
    snapshot_index = 0
    stored = 0
    for index, event in enumerate(planned_events(when)):
        camera = cameras.get(event.source)
        sensor = sensors.get(event.source)
        zone = zones.get((event.source, event.event_type))
        row = Event(
            organization_id=organization.id,
            camera_id=camera.id if camera is not None else None,
            sensor_id=sensor.id if sensor is not None else None,
            zone_id=zone.id if zone is not None else None,
            event_type=event.event_type,
            severity=event.severity,
            status=event.status,
            reviewed_at=event.reviewed_at,
            occurred_at=event.occurred_at,
            client_event_id=f"{id_prefix}-{index:02d}",
        )
        db.add(row)
        db.flush()
        if event.snapshot:
            payload = frames[snapshot_index % len(frames)]
            snapshot_index += 1
            key = f"{organization.id}/{row.id}.jpg"
            row.snapshot_key = key
            store(key, payload)
            stored += 1
    for camera in cameras.values():
        for usage_day in usage_dates(when):
            db.add(
                UsageRecord(
                    organization_id=organization.id,
                    camera_id=camera.id,
                    usage_date=usage_day,
                    analyzed_minutes=minutes_for(camera.name, usage_day),
                )
            )
    db.flush()
    return DemoResult(
        organization_id=organization.id,
        organization_name=name,
        email=email.strip().lower(),
        full_name=full_name.strip(),
        events=len(EVENTS),
        snapshots=stored,
    )


def _camera(organization_id: uuid.UUID, site_id: uuid.UUID, name: str) -> Camera:
    return Camera(
        organization_id=organization_id,
        site_id=site_id,
        name=name,
        source_type="file",
        file_path="/videos/demo1.mp4",
        fps=2,
        enabled=False,
        loop=False,
    )


def _zone(
    organization_id: uuid.UUID,
    camera_id: uuid.UUID,
    name: str,
    rule_type: str,
    params: dict,
    start: str = "00:00",
    end: str = "23:59",
    polygon: list | None = None,
) -> Zone:
    return Zone(
        organization_id=organization_id,
        camera_id=camera_id,
        name=name,
        polygon=polygon or [[0.15, 0.2], [0.85, 0.2], [0.9, 0.95], [0.1, 0.95]],
        schedule=_schedule(start, end),
        rule_type=rule_type,
        rule_params=params,
    )


def _sensor(
    organization_id: uuid.UUID, site_id: uuid.UUID, name: str, sensor_type: str, external_id: str
) -> Sensor:
    return Sensor(
        organization_id=organization_id,
        site_id=site_id,
        name=name,
        sensor_type=sensor_type,
        external_id=external_id,
    )
