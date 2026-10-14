import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.entities import User
from app.schemas.auth import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger("sentinel.api")


@router.get("", response_model=list[UserRead])
def list_users(
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[User]:
    return list(
        db.scalars(
            select(User).where(User.organization_id == user.organization_id).order_by(User.created_at.desc()).limit(200)
        )
    )


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    created = User(
        organization_id=user.organization_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(created)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ese correo ya está registrado") from None
    db.refresh(created)
    logger.info("user created org=%s user=%s role=%s", user.organization_id, created.id, created.role)
    return created
