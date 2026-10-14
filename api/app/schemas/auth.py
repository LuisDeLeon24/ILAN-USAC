import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.common import clean_name, normalize_email


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        return normalize_email(value)


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Literal["admin", "operator"]
    organization_id: uuid.UUID
    organization_name: str


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: Literal["admin", "operator"]

    @field_validator("email")
    @classmethod
    def normalize_user_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("password")
    @classmethod
    def password_length(cls, value: str) -> str:
        if len(value) < 8 or len(value) > 128:
            raise ValueError("La contraseña debe tener entre 8 y 128 caracteres")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: Literal["admin", "operator"]
    created_at: datetime
