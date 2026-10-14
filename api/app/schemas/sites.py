import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.common import clean_name, clean_optional_text


class SiteCreate(BaseModel):
    name: str
    address: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("address")
    @classmethod
    def normalize_address(cls, value: str | None) -> str | None:
        return clean_optional_text(value, 500)


class SiteUpdate(SiteCreate):
    pass


class SiteRead(BaseModel):
    id: uuid.UUID
    name: str
    address: str | None
    camera_count: int
    created_at: datetime
