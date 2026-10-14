import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AgentMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    site_id: uuid.UUID | None = None

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Escribe una pregunta")
        return cleaned


class AgentActionIn(BaseModel):
    id: uuid.UUID


class AgentMessageRead(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AgentConfirmationRead(BaseModel):
    id: uuid.UUID
    prompt: str


class AgentThreadRead(BaseModel):
    messages: list[AgentMessageRead]
    confirmation: AgentConfirmationRead | None
