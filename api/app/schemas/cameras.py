import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from app.schemas.common import clean_name, clean_optional_text


def validate_fps(value: int) -> int:
    if value < 2 or value > 5:
        raise ValueError("Los cuadros por segundo deben estar entre 2 y 5")
    return value


def validate_confidence(value: float) -> float:
    if isinstance(value, bool) or value < 0.05 or value > 0.95:
        raise ValueError("La confianza mínima debe estar entre 0.05 y 0.95")
    return round(float(value), 2)


def validate_box_area(value: float) -> float:
    if isinstance(value, bool) or value < 0 or value > 1:
        raise ValueError("El tamaño mínimo debe estar entre 0 y 1")
    return round(float(value), 4)


class CameraCreate(BaseModel):
    site_id: uuid.UUID
    name: str
    source_type: Literal["rtsp", "file"]
    rtsp_url: str | None = None
    file_path: str | None = None
    fps: int = 2
    enabled: bool = True
    loop: bool = False
    min_confidence: float = 0.35
    min_box_area: float = 0

    @field_validator("min_confidence")
    @classmethod
    def normalize_confidence(cls, value: float) -> float:
        return validate_confidence(value)

    @field_validator("min_box_area")
    @classmethod
    def normalize_box_area(cls, value: float) -> float:
        return validate_box_area(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("fps")
    @classmethod
    def normalize_fps(cls, value: int) -> int:
        return validate_fps(value)

    @field_validator("file_path")
    @classmethod
    def normalize_path(cls, value: str | None) -> str | None:
        return clean_optional_text(value, 500)

    @model_validator(mode="after")
    def source_requirements(self) -> "CameraCreate":
        if self.source_type == "rtsp":
            url = (self.rtsp_url or "").strip()
            if not url.startswith("rtsp://"):
                raise ValueError("La URL debe comenzar con rtsp://")
            if len(url) > 2000:
                raise ValueError("La URL es demasiado larga")
            self.rtsp_url = url
            self.file_path = None
            self.loop = False
        else:
            if not self.file_path:
                raise ValueError("Indica la ruta del archivo")
            self.rtsp_url = None
        return self


class CameraUpdate(BaseModel):
    site_id: uuid.UUID | None = None
    name: str | None = None
    source_type: Literal["rtsp", "file"] | None = None
    rtsp_url: str | None = None
    file_path: str | None = None
    fps: int | None = None
    enabled: bool | None = None
    loop: bool | None = None
    min_confidence: float | None = None
    min_box_area: float | None = None

    @field_validator("min_confidence")
    @classmethod
    def normalize_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return validate_confidence(value)

    @field_validator("min_box_area")
    @classmethod
    def normalize_box_area(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return validate_box_area(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_name(value)

    @field_validator("fps")
    @classmethod
    def normalize_fps(cls, value: int | None) -> int | None:
        if value is None:
            return None
        return validate_fps(value)

    @field_validator("rtsp_url")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not cleaned.startswith("rtsp://"):
            raise ValueError("La URL debe comenzar con rtsp://")
        if len(cleaned) > 2000:
            raise ValueError("La URL es demasiado larga")
        return cleaned

    @field_validator("file_path")
    @classmethod
    def normalize_path(cls, value: str | None) -> str | None:
        return clean_optional_text(value, 500)


class LiveTokenRead(BaseModel):
    token: str
    expires_at: datetime
    stream_url: str
    status_url: str


class CameraRead(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    source_type: Literal["rtsp", "file"]
    rtsp_url_masked: str | None
    file_path: str | None
    fps: int
    enabled: bool
    loop: bool
    min_confidence: float
    min_box_area: float
    zone_count: int
    created_at: datetime
