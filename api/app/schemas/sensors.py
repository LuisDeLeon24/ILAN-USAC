import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from app.schemas.common import clean_name

SensorType = Literal["door", "motion", "smoke", "panic"]
SensorEventType = Literal["door_open", "motion", "smoke", "panic"]
SENSOR_EVENTS: dict[str, tuple[str, str]] = {
    "door": ("door_open", "medium"),
    "motion": ("motion", "low"),
    "smoke": ("smoke", "critical"),
    "panic": ("panic", "critical"),
}


def clean_external_id(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("El identificador es obligatorio")
    if len(cleaned) > 200:
        raise ValueError("El identificador es demasiado largo")
    return cleaned


class SensorWrite(BaseModel):
    site_id: uuid.UUID
    name: str
    sensor_type: SensorType
    external_id: str

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("external_id")
    @classmethod
    def normalize_external_id(cls, value: str) -> str:
        return clean_external_id(value)


class SensorRead(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    sensor_type: SensorType
    external_id: str
    created_at: datetime
