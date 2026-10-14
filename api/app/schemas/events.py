import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Status = Literal["new", "in_review", "resolved", "false_positive"]
Severity = Literal["low", "medium", "high", "critical"]


class EventRead(BaseModel):
    id: uuid.UUID
    event_type: str
    severity: Severity
    status: Status
    camera_id: uuid.UUID | None
    camera_name: str | None
    sensor_id: uuid.UUID | None
    sensor_name: str | None
    occurred_at: datetime
    reviewed_at: datetime | None
    has_snapshot: bool


class EventStatusWrite(BaseModel):
    status: Status
