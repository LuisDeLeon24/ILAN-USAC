import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from app.core.config import DEFAULT_TIMEZONE
from app.schemas.common import clean_name, normalize_polygon

DAY = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
RULE = Literal["intrusion", "after_hours", "loitering", "occupancy"]
TIME_PATTERN = re.compile(r"\d{2}:\d{2}")


class ScheduleWindow(BaseModel):
    days: list[DAY]
    start: str
    end: str

    @field_validator("days")
    @classmethod
    def days_present(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Selecciona al menos un día")
        if len(set(value)) != len(value):
            raise ValueError("Hay días repetidos")
        return value

    @field_validator("start", "end")
    @classmethod
    def clock(cls, value: str) -> str:
        if TIME_PATTERN.fullmatch(value) is None:
            raise ValueError("La hora debe usar el formato HH:MM")
        hour, minute = int(value[:2]), int(value[3:])
        if hour > 23 or minute > 59:
            raise ValueError("La hora no es válida")
        return value

    @model_validator(mode="after")
    def end_after_start(self) -> "ScheduleWindow":
        if self.start >= self.end:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        return self


class Schedule(BaseModel):
    timezone: str = DEFAULT_TIMEZONE
    windows: list[ScheduleWindow]

    @field_validator("timezone")
    @classmethod
    def timezone_supported(cls, value: str) -> str:
        if value != DEFAULT_TIMEZONE:
            raise ValueError("La zona horaria debe ser America/Guatemala")
        return value

    @field_validator("windows")
    @classmethod
    def windows_present(cls, value: list[ScheduleWindow]) -> list[ScheduleWindow]:
        if not value:
            raise ValueError("Agrega al menos un horario")
        return value


class ZoneWrite(BaseModel):
    name: str
    polygon: list[list[float]]
    schedule: Schedule
    rule_type: RULE
    rule_params: dict = {}

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("polygon")
    @classmethod
    def check_polygon(cls, value: list[list[float]]) -> list[list[float]]:
        return normalize_polygon(value)

    @model_validator(mode="after")
    def normalize_params(self) -> "ZoneWrite":
        params = self.rule_params or {}
        if self.rule_type == "loitering":
            seconds = params.get("seconds")
            if isinstance(seconds, bool) or not isinstance(seconds, int) or seconds <= 0:
                raise ValueError("Merodeo requiere segundos mayores a 0")
            self.rule_params = {"seconds": seconds}
        elif self.rule_type == "occupancy":
            max_people = params.get("max_people")
            if isinstance(max_people, bool) or not isinstance(max_people, int) or max_people < 1:
                raise ValueError("Ocupación requiere un máximo de personas de al menos 1")
            self.rule_params = {"max_people": max_people}
        else:
            self.rule_params = {}
        return self


class ZoneRead(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    name: str
    polygon: list[list[float]]
    schedule: Schedule
    rule_type: RULE
    rule_params: dict
    created_at: datetime
