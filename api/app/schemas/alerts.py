import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from app.schemas.common import clean_name

AlertStatus = Literal["sent", "failed", "suppressed"]
AlertChannel = Literal["whatsapp", "telegram"]
_PHONE = re.compile(r"^\+[1-9]\d{7,14}$")
_CHAT_ID = re.compile(r"^-?[1-9]\d{0,19}$")


def clean_phone(value: str) -> str:
    cleaned = value.strip().replace(" ", "")
    if cleaned.lower().startswith("whatsapp:"):
        cleaned = cleaned.split(":", 1)[1]
    if not _PHONE.fullmatch(cleaned):
        raise ValueError("El número debe estar en formato internacional, por ejemplo +50255555555")
    return cleaned


def clean_chat_id(value: str) -> str:
    cleaned = value.strip()
    if not _CHAT_ID.fullmatch(cleaned):
        raise ValueError("El chat de Telegram no es válido")
    return cleaned


class AlertContactWrite(BaseModel):
    name: str
    channel: str = "whatsapp"
    phone: str | None = None
    chat_id: str | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("channel", mode="before")
    @classmethod
    def normalize_channel(cls, value: object) -> str:
        if value not in ("whatsapp", "telegram"):
            raise ValueError("El canal debe ser WhatsApp o Telegram")
        return str(value)

    @model_validator(mode="after")
    def channel_identity(self) -> "AlertContactWrite":
        if self.channel == "whatsapp":
            if self.chat_id:
                raise ValueError("Un contacto de WhatsApp no lleva chat de Telegram")
            if not self.phone or not self.phone.strip():
                raise ValueError("El número debe estar en formato internacional, por ejemplo +50255555555")
            self.phone = clean_phone(self.phone)
            self.chat_id = None
            return self
        if self.phone and self.phone.strip():
            raise ValueError("Un contacto de Telegram no lleva número de WhatsApp")
        if not self.chat_id or not self.chat_id.strip():
            raise ValueError("Elige un chat de Telegram")
        self.chat_id = clean_chat_id(self.chat_id)
        self.phone = None
        return self


class AlertContactRead(BaseModel):
    id: uuid.UUID
    name: str
    channel: AlertChannel
    phone: str | None
    chat_id: str | None
    enabled: bool
    created_at: datetime


class TelegramChatRead(BaseModel):
    chat_id: str
    label: str
    username: str | None


class AlertLogRead(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID | None
    event_type: str | None
    contact_name: str | None
    provider: str
    status: AlertStatus
    detail: str | None
    is_test: bool
    created_at: datetime


class TestAlertResult(BaseModel):
    message: str
