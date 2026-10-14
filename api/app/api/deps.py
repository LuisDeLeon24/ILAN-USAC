import uuid
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token, hash_device_token
from app.db.session import get_db
from app.models.entities import Device, User


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sesión inválida")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Sesión inválida") from None
    user = db.get(User, user_id)
    if user is None or str(user.organization_id) != payload.get("org"):
        raise HTTPException(status_code=401, detail="Sesión inválida")
    return user


def get_device(
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> Device:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Dispositivo no autorizado")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Dispositivo no autorizado")
    device = db.scalar(select(Device).where(Device.token_hash == hash_device_token(token)))
    if device is None:
        raise HTTPException(status_code=401, detail="Dispositivo no autorizado")
    return device


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="No tienes permiso para esta acción")
    return user


def scoped_get(db: Session, model: type, user: User, object_id: uuid.UUID):
    row = db.scalar(select(model).where(model.id == object_id, model.organization_id == user.organization_id))
    if row is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return row
