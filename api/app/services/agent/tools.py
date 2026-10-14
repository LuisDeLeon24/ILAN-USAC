import logging
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import Camera, Device, Event, Sensor, Site, UsageRecord, User
from app.services.agent.dates import resolve_window
from app.services.event_status import apply_event_status
from app.services.pricing import ensure_pricing_plan

logger = logging.getLogger("sentinel.agent")

SEARCH_LIMIT = 20
DEVICE_ONLINE = timedelta(seconds=90)
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
STATUSES = {"new", "in_review", "resolved", "false_positive"}
EVENT_LABELS = {
    "intrusion": "intrusión",
    "after_hours": "fuera de horario",
    "loitering": "merodeo",
    "occupancy": "ocupación",
    "camera_disconnected": "cámara desconectada",
    "door_open": "puerta abierta",
    "motion": "movimiento",
    "smoke": "humo",
    "panic": "botón de pánico",
}
SEVERITY_LABELS = {"low": "baja", "medium": "media", "high": "alta", "critical": "crítico"}
STATUS_LABELS = {
    "new": "nuevo",
    "in_review": "en revisión",
    "resolved": "resuelto",
    "false_positive": "falso positivo",
}
_PERIOD = {
    "type": "string",
    "enum": ["today", "yesterday", "this_week", "last_night", "this_month"],
    "description": "today hoy, yesterday ayer, this_week esta semana desde el lunes, last_night anoche de 20:00 a 06:00, this_month este mes. Zona America/Guatemala.",
}
_FILTERS = {
    "period": _PERIOD,
    "start": {"type": "string", "description": "Fecha inicial AAAA-MM-DD en America/Guatemala"},
    "end": {"type": "string", "description": "Fecha final AAAA-MM-DD en America/Guatemala"},
    "event_type": {"type": "string", "enum": sorted(EVENT_TYPES)},
    "severity": {"type": "string", "enum": sorted(SEVERITIES)},
    "status": {"type": "string", "enum": sorted(STATUSES)},
    "camera_name": {"type": "string"},
    "sensor_name": {"type": "string"},
    "site_name": {"type": "string"},
}

TOOL_SCHEMAS = [
    {
        "name": "search_events",
        "description": "Busca eventos de esta organización. Devuelve como máximo 20, del más reciente al más antiguo.",
        "parameters": {"type": "object", "properties": _FILTERS},
    },
    {
        "name": "count_events",
        "description": "Cuenta eventos de esta organización. group_by puede ser event_type, severity, status o camera.",
        "parameters": {
            "type": "object",
            "properties": {**_FILTERS, "group_by": {"type": "string", "enum": ["event_type", "severity", "status", "camera"]}},
        },
    },
    {
        "name": "summarize_events",
        "description": "Resume un periodo con totales por tipo, severidad, estado y lugar. No inventes cifras fuera de este resultado.",
        "parameters": {"type": "object", "properties": _FILTERS},
    },
    {
        "name": "get_event",
        "description": "Detalle de un evento de esta organización. El id sale de una búsqueda anterior.",
        "parameters": {
            "type": "object",
            "properties": {"event_id": {"type": "string"}},
            "required": ["event_id"],
        },
    },
    {
        "name": "change_event_status",
        "description": "Propone cambiar el estado de un evento. No se aplica hasta que la persona lo confirme en el chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "status": {"type": "string", "enum": sorted(STATUSES)},
            },
            "required": ["event_id", "status"],
        },
    },
    {
        "name": "get_usage",
        "description": "Minutos analizados y costo estimado del periodo. La tarifa solo se consulta; no se puede cambiar desde el chat.",
        "parameters": {"type": "object", "properties": {"period": _PERIOD, "start": _FILTERS["start"], "end": _FILTERS["end"]}},
    },
    {
        "name": "get_equipment_status",
        "description": "Estado de las cámaras y de los dispositivos de borde de esta organización.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "briefing",
        "description": (
            "Una sola consulta para intrusiones de esta semana, eventos críticos de ayer, "
            "o minutos y costo de este mes. Úsala en lugar de varias herramientas."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": ["intrusions_this_week", "critical_yesterday", "usage_this_month"],
                }
            },
            "required": ["topic"],
        },
    },
]

BRIEFING_TOPICS = {"intrusions_this_week", "critical_yesterday", "usage_this_month"}
SUGGESTED_QUESTIONS = {
    "cuantas intrusiones hubo esta semana": "intrusions_this_week",
    "resume los eventos criticos de ayer": "critical_yesterday",
    "cuantos minutos se analizaron este mes y cual es el costo estimado": "usage_this_month",
}


class EventFilter(BaseModel):
    model_config = ConfigDict(extra="ignore")
    period: str | None = None
    start: str | None = None
    end: str | None = None
    event_type: str | None = None
    severity: str | None = None
    status: str | None = None
    camera_name: str | None = None
    sensor_name: str | None = None
    site_name: str | None = None
    group_by: str | None = None


def execute_tool(
    name: str,
    arguments: dict,
    db: Session,
    user: User,
    site_id: uuid.UUID | None = None,
) -> tuple[dict, str, str]:
    if name == "change_event_status":
        return {"error": "Esta acción requiere confirmación"}, "rejected", "Requiere confirmación"
    if name not in {tool["name"] for tool in TOOL_SCHEMAS}:
        return {"error": "Herramienta no disponible"}, "rejected", "Herramienta no disponible"
    try:
        if name == "search_events":
            result = _search(db, user, arguments, site_id)
        elif name == "count_events":
            result = _count(db, user, arguments, site_id)
        elif name == "summarize_events":
            result = _summarize(db, user, arguments, site_id)
        elif name == "get_event":
            result = _detail(db, user, arguments, site_id)
        elif name == "get_usage":
            result = _usage(db, user, arguments, site_id)
        elif name == "briefing":
            result = _briefing(db, user, arguments, site_id)
        else:
            result = _equipment(db, user, site_id)
    except ValueError as exc:
        return {"error": str(exc)}, "rejected", str(exc)
    if "error" in result and len(result) == 1:
        return result, "rejected", str(result["error"])
    return result, "executed", "ok"


def scope_name(db: Session, user: User, site_id: uuid.UUID | None) -> str | None:
    if site_id is None:
        return None
    name = db.scalar(select(Site.name).where(Site.id == site_id, Site.organization_id == user.organization_id))
    if name is None:
        raise LookupError("Ese sitio no está en tu organización.")
    return str(name)


def prepare_status_change(
    arguments: dict,
    db: Session,
    user: User,
    site_id: uuid.UUID | None = None,
) -> tuple[dict, str, str]:
    try:
        status = _enum(arguments.get("status") if isinstance(arguments, dict) else None, STATUSES, "Estado")
        event_id = _uuid(arguments.get("event_id") if isinstance(arguments, dict) else None)
    except ValueError as exc:
        return {"error": str(exc)}, "rejected", str(exc)
    if status is None or event_id is None:
        return {"error": "Faltan el evento y el estado"}, "rejected", "Argumentos incompletos"
    row = _load_event(db, user, event_id, site_id)
    if row is None:
        return {"error": "Evento no encontrado"}, "rejected", "Evento no encontrado"
    event, camera_name, sensor_name, _site_name = row
    prompt = (
        f"¿Confirmas marcar el evento de {EVENT_LABELS.get(event.event_type, 'evento')} "
        f"en {camera_name or sensor_name or 'la organización'} del {_when(event.occurred_at)} "
        f"como {STATUS_LABELS[status]}?"
    )
    confirmation = {
        "id": str(uuid.uuid4()),
        "event_id": str(event.id),
        "status": status,
        "prompt": prompt,
    }
    return {"confirmation": confirmation}, "pending_confirmation", prompt


def apply_confirmed_status(db: Session, user: User, event_id: uuid.UUID, status: str) -> str:
    event = db.scalar(select(Event).where(Event.id == event_id, Event.organization_id == user.organization_id))
    if event is None:
        return "Ese evento ya no está disponible."
    apply_event_status(event, status)
    logger.info("event status org=%s event=%s status=%s", user.organization_id, event.id, status)
    return f"Listo. El evento quedó como {STATUS_LABELS[status]}."


def _search(db: Session, user: User, arguments: dict, site_id: uuid.UUID | None = None) -> dict:
    filters = _filters(arguments)
    start, end = resolve_window(filters.period, filters.start, filters.end)
    rows = db.execute(
        _event_query(user, filters, start, end, site_id).order_by(Event.occurred_at.desc()).limit(SEARCH_LIMIT)
    ).all()
    total = db.scalar(_count_query(user, filters, start, end, site_id)) or 0
    return {
        "total": int(total),
        "inicio": start.isoformat(),
        "fin": end.isoformat(),
        "eventos": [_public(*row) for row in rows],
    }


def _count(db: Session, user: User, arguments: dict, site_id: uuid.UUID | None = None) -> dict:
    filters = _filters(arguments)
    start, end = resolve_window(filters.period, filters.start, filters.end)
    grouped = _enum(filters.group_by, {"event_type", "severity", "status", "camera"}, "Agrupación")
    total = db.scalar(_count_query(user, filters, start, end, site_id)) or 0
    result: dict = {"total": int(total), "inicio": start.isoformat(), "fin": end.isoformat()}
    if grouped:
        result["grupos"] = _groups(db, user, filters, start, end, grouped, site_id)
    return result


def _summarize(db: Session, user: User, arguments: dict, site_id: uuid.UUID | None = None) -> dict:
    filters = _filters(arguments)
    if not filters.period and not (filters.start and filters.end):
        filters.period = "this_week"
    start, end = resolve_window(filters.period, filters.start, filters.end)
    total = db.scalar(_count_query(user, filters, start, end, site_id)) or 0
    return {
        "total": int(total),
        "inicio": start.isoformat(),
        "fin": end.isoformat(),
        "por_tipo": _groups(db, user, filters, start, end, "event_type", site_id),
        "por_severidad": _groups(db, user, filters, start, end, "severity", site_id),
        "por_estado": _groups(db, user, filters, start, end, "status", site_id),
        "por_lugar": _groups(db, user, filters, start, end, "camera", site_id),
    }


def _detail(db: Session, user: User, arguments: dict, site_id: uuid.UUID | None = None) -> dict:
    event_id = _uuid(arguments.get("event_id") if isinstance(arguments, dict) else None)
    if event_id is None:
        raise ValueError("Falta el evento")
    row = _load_event(db, user, event_id, site_id)
    if row is None:
        return {"error": "Evento no encontrado"}
    event, camera_name, sensor_name, site_name = row
    payload = _public(event, camera_name, sensor_name, site_name)
    payload["revisado"] = _when(event.reviewed_at) if event.reviewed_at else None
    return payload


def normalize_question(value: str) -> str:
    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def suggested_answer(db: Session, user: User, content: str, site_id: uuid.UUID | None = None) -> str | None:
    topic = SUGGESTED_QUESTIONS.get(normalize_question(content))
    if topic is None:
        return None
    return str(_briefing(db, user, {"topic": topic}, site_id)["respuesta"])


def render_briefing(db: Session, user: User, topic: str, site_id: uuid.UUID | None = None) -> str:
    place = ""
    site = scope_name(db, user, site_id)
    if site:
        place = f" en {site}"
    if topic == "intrusions_this_week":
        total = int(_count(db, user, {"period": "this_week", "event_type": "intrusion"}, site_id)["total"])
        if total == 1:
            return f"Esta semana hubo 1 intrusión{place}."
        return f"Esta semana hubo {total} intrusiones{place}."
    if topic == "critical_yesterday":
        found = _search(db, user, {"period": "yesterday", "severity": "critical"}, site_id)
        total = int(found["total"])
        if total == 0:
            return f"Ayer no hubo eventos críticos{place}."
        details = []
        for item in found["eventos"]:
            spot = item.get("lugar") or "la organización"
            site_label = item.get("sitio")
            where = f"{spot}, {site_label}" if site_label else str(spot)
            details.append(f"{item['tipo']} en {where} ({item['cuando']})")
        noun = "evento crítico" if total == 1 else "eventos críticos"
        return f"Ayer hubo {total} {noun}{place}: {'; '.join(details)}."
    usage = _usage(db, user, {"period": "this_month"}, site_id)
    return (
        f"Este mes se analizaron {usage['minutos_analizados']} minutos{place}. "
        f"La tarifa es {usage['tarifa_por_minuto']} {usage['moneda']} por minuto "
        f"y el costo estimado es {usage['costo_estimado']} {usage['moneda']}."
    )


def _briefing(db: Session, user: User, arguments: dict, site_id: uuid.UUID | None = None) -> dict:
    if not isinstance(arguments, dict):
        raise ValueError("Argumentos no válidos")
    topic = _enum(arguments.get("topic"), BRIEFING_TOPICS, "Tema")
    if topic is None:
        raise ValueError("Falta el tema")
    return {"tema": topic, "respuesta": render_briefing(db, user, topic, site_id)}


def _usage(db: Session, user: User, arguments: dict, site_id: uuid.UUID | None = None) -> dict:
    filters = _filters(arguments)
    if not filters.period and not (filters.start and filters.end):
        filters.period = "this_month"
    start, end = resolve_window(filters.period, filters.start, filters.end)
    plan = ensure_pricing_plan(db, user.organization_id)
    usage_query = select(func.coalesce(func.sum(UsageRecord.analyzed_minutes), 0)).where(
        UsageRecord.organization_id == user.organization_id,
        UsageRecord.usage_date >= start.date(),
        UsageRecord.usage_date < end.date(),
    )
    if site_id is not None:
        usage_query = usage_query.join(Camera, Camera.id == UsageRecord.camera_id).where(Camera.site_id == site_id)
    minutes = db.scalar(usage_query)
    analyzed = Decimal(minutes or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rate = Decimal(plan.rate_per_minute)
    cost = (analyzed * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "inicio": start.date().isoformat(),
        "fin": end.date().isoformat(),
        "minutos_analizados": f"{analyzed:.2f}",
        "costo_estimado": f"{cost:.2f}",
        "moneda": plan.currency,
        "tarifa_por_minuto": f"{rate:.4f}",
    }


def _equipment(db: Session, user: User, site_id: uuid.UUID | None = None) -> dict:
    moment = datetime.now(timezone.utc)
    cameras_query = (
        select(Camera, Site.name)
        .join(Site, Site.id == Camera.site_id)
        .where(Camera.organization_id == user.organization_id)
        .order_by(Camera.name)
    )
    devices_query = (
        select(Device, Site.name)
        .join(Site, Site.id == Device.site_id)
        .where(Device.organization_id == user.organization_id)
        .order_by(Device.name)
    )
    if site_id is not None:
        cameras_query = cameras_query.where(Camera.site_id == site_id)
        devices_query = devices_query.where(Device.site_id == site_id)
    cameras = db.execute(cameras_query).all()
    devices = db.execute(devices_query).all()
    return {
        "camaras": [
            {
                "nombre": camera.name,
                "sitio": site_name,
                "estado": "habilitada" if camera.enabled else "deshabilitada",
                "origen": "archivo" if camera.source_type == "file" else "rtsp",
            }
            for camera, site_name in cameras
        ],
        "dispositivos": [
            {
                "nombre": device.name,
                "sitio": site_name,
                "modelo": device.model_version or "sin reporte",
                "visto": _when(device.last_seen_at) if device.last_seen_at else "sin reporte",
                "estado": "en línea" if device.last_seen_at and device.last_seen_at >= moment - DEVICE_ONLINE else "sin conexión",
            }
            for device, site_name in devices
        ],
    }


def _filters(arguments: dict) -> EventFilter:
    if not isinstance(arguments, dict):
        raise ValueError("Argumentos no válidos")
    filters = EventFilter.model_validate(arguments)
    filters.event_type = _enum(filters.event_type, EVENT_TYPES, "Tipo de evento")
    filters.severity = _enum(filters.severity, SEVERITIES, "Severidad")
    filters.status = _enum(filters.status, STATUSES, "Estado")
    return filters


def _event_query(user: User, filters: EventFilter, start: datetime, end: datetime, site_id: uuid.UUID | None = None):
    query = (
        select(Event, Camera.name, Sensor.name, Site.name)
        .outerjoin(Camera, Camera.id == Event.camera_id)
        .outerjoin(Sensor, Sensor.id == Event.sensor_id)
        .outerjoin(Site, or_(Site.id == Camera.site_id, Site.id == Sensor.site_id))
    )
    return _restrict(query, user, filters, start, end, site_id)


def _count_query(user: User, filters: EventFilter, start: datetime, end: datetime, site_id: uuid.UUID | None = None):
    query = select(func.count(Event.id.distinct())).select_from(Event)
    query = query.outerjoin(Camera, Camera.id == Event.camera_id).outerjoin(Sensor, Sensor.id == Event.sensor_id)
    query = query.outerjoin(Site, or_(Site.id == Camera.site_id, Site.id == Sensor.site_id))
    return _restrict(query, user, filters, start, end, site_id)


def _restrict(query, user: User, filters: EventFilter, start: datetime, end: datetime, site_id: uuid.UUID | None = None):
    query = query.where(
        Event.organization_id == user.organization_id,
        Event.occurred_at >= start,
        Event.occurred_at < end,
    )
    if filters.event_type:
        query = query.where(Event.event_type == filters.event_type)
    if filters.severity:
        query = query.where(Event.severity == filters.severity)
    if filters.status:
        query = query.where(Event.status == filters.status)
    if filters.camera_name:
        query = query.where(Camera.name.ilike(_contains(filters.camera_name), escape="\\"))
    if filters.sensor_name:
        query = query.where(Sensor.name.ilike(_contains(filters.sensor_name), escape="\\"))
    if filters.site_name:
        query = query.where(Site.name.ilike(_contains(filters.site_name), escape="\\"))
    if site_id is not None:
        query = query.where(Site.id == site_id)
    return query


def _groups(
    db: Session,
    user: User,
    filters: EventFilter,
    start: datetime,
    end: datetime,
    grouped: str,
    site_id: uuid.UUID | None = None,
) -> dict[str, int]:
    if grouped == "camera":
        column = func.coalesce(Camera.name, Sensor.name)
    elif grouped == "event_type":
        column = Event.event_type
    elif grouped == "severity":
        column = Event.severity
    else:
        column = Event.status
    query = select(column, func.count(Event.id.distinct())).select_from(Event)
    query = query.outerjoin(Camera, Camera.id == Event.camera_id).outerjoin(Sensor, Sensor.id == Event.sensor_id)
    query = query.outerjoin(Site, or_(Site.id == Camera.site_id, Site.id == Sensor.site_id))
    rows = db.execute(_restrict(query, user, filters, start, end, site_id).group_by(column)).all()
    labeled: dict[str, int] = {}
    for key, count in rows:
        if grouped == "event_type":
            name = EVENT_LABELS.get(key, "sin tipo")
        elif grouped == "severity":
            name = SEVERITY_LABELS.get(key, "sin severidad")
        elif grouped == "status":
            name = STATUS_LABELS.get(key, "sin estado")
        else:
            name = key or "sin lugar"
        labeled[name] = labeled.get(name, 0) + int(count)
    return labeled


def _load_event(db: Session, user: User, event_id: uuid.UUID, site_id: uuid.UUID | None = None):
    start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    end = datetime(2100, 1, 1, tzinfo=timezone.utc)
    filters = EventFilter()
    return db.execute(_event_query(user, filters, start, end, site_id).where(Event.id == event_id)).first()


def _public(event: Event, camera_name: str | None, sensor_name: str | None, site_name: str | None) -> dict:
    return {
        "id": str(event.id),
        "tipo": EVENT_LABELS.get(event.event_type, event.event_type),
        "severidad": SEVERITY_LABELS.get(event.severity, event.severity),
        "estado": STATUS_LABELS.get(event.status, event.status),
        "lugar": camera_name or sensor_name,
        "sitio": site_name,
        "cuando": _when(event.occurred_at),
    }


def _when(value: datetime) -> str:
    from app.services.agent.dates import GUATEMALA

    return value.astimezone(GUATEMALA).strftime("%d/%m/%Y %H:%M")


def _contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _enum(value: str | None, allowed: set[str], label: str) -> str | None:
    if value is None or not str(value).strip():
        return None
    cleaned = str(value).strip()
    if cleaned not in allowed:
        raise ValueError(f"{label} no válido")
    return cleaned


def _uuid(value: object) -> uuid.UUID | None:
    if value is None or not str(value).strip():
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise ValueError("Evento no válido") from None
