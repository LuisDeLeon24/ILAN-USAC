import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.schemas.sensors import SensorEventType

EventType = Literal["intrusion", "after_hours", "loitering", "occupancy", "camera_disconnected"]
SEVERITY_FOR_TYPE = {
    "intrusion": "high",
    "after_hours": "high",
    "loitering": "medium",
    "occupancy": "medium",
    "camera_disconnected": "high",
}


class HeartbeatWrite(BaseModel):
    model_version: str

    @field_validator("model_version")
    @classmethod
    def model_version_present(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 64:
            raise ValueError("Versión de modelo no válida")
        return cleaned


class DeviceEventWrite(BaseModel):
    client_event_id: str
    camera_id: uuid.UUID
    zone_id: uuid.UUID | None = None
    event_type: EventType
    occurred_at: datetime

    @field_validator("client_event_id")
    @classmethod
    def event_id_present(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 64:
            raise ValueError("Identificador de evento no válido")
        return cleaned

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("La fecha del evento debe incluir zona horaria")
        return value


class DeviceEventResult(BaseModel):
    id: uuid.UUID
    created: bool


class DeviceSensorEventWrite(BaseModel):
    client_event_id: str
    sensor_id: uuid.UUID
    event_type: SensorEventType
    occurred_at: datetime

    @field_validator("client_event_id")
    @classmethod
    def sensor_event_id_present(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 64:
            raise ValueError("Identificador de evento no válido")
        return cleaned

    @field_validator("occurred_at")
    @classmethod
    def sensor_occurred_at_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("La fecha del evento debe incluir zona horaria")
        return value


class DeviceUsageWrite(BaseModel):
    client_report_id: str
    camera_id: uuid.UUID
    usage_date: date
    analyzed_minutes: float

    @field_validator("client_report_id")
    @classmethod
    def report_id_present(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 64:
            raise ValueError("Identificador de reporte no válido")
        return cleaned

    @field_validator("analyzed_minutes")
    @classmethod
    def minutes_positive(cls, value: float) -> float:
        if isinstance(value, bool) or value <= 0 or value > 240:
            raise ValueError("Los minutos analizados no son válidos")
        return float(value)


class DeviceUsageResult(BaseModel):
    analyzed_minutes: float
    created: bool


class DeviceFrameResult(BaseModel):
    received: bool


class ZoneConfig(BaseModel):
    id: uuid.UUID
    name: str
    polygon: list
    schedule: dict
    rule_type: str
    rule_params: dict


class ExclusionConfig(BaseModel):
    id: uuid.UUID
    polygon: list


class CameraConfig(BaseModel):
    id: uuid.UUID
    name: str
    source_type: Literal["rtsp", "file"]
    file_path: str | None
    rtsp_url: str | None
    fps: int
    loop: bool
    min_confidence: float
    min_box_area: float
    frame_requested: bool
    zones: list[ZoneConfig]
    exclusions: list[ExclusionConfig]


class SensorConfig(BaseModel):
    id: uuid.UUID
    name: str
    sensor_type: str
    external_id: str


class DeviceConfig(BaseModel):
    device_id: uuid.UUID
    site_id: uuid.UUID
    organization_id: uuid.UUID
    timezone: str
    cooldown_seconds: int
    cameras: list[CameraConfig]
    sensors: list[SensorConfig]
