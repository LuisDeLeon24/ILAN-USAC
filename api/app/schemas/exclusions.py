import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.common import normalize_polygon


class ExclusionWrite(BaseModel):
    polygon: list[list[float]]

    @field_validator("polygon")
    @classmethod
    def check_polygon(cls, value: list[list[float]]) -> list[list[float]]:
        return normalize_polygon(value)


class ExclusionRead(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    polygon: list[list[float]]
    created_at: datetime
