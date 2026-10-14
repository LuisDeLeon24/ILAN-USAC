from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.entities import Organization, User
from app.schemas.auth import LoginRequest, MeRead, TokenRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenRead)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenRead:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    token = create_access_token(user_id=user.id, organization_id=user.organization_id, role=user.role)
    return TokenRead(access_token=token)


@router.get("/me", response_model=MeRead)
def me(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> MeRead:
    organization = db.get(Organization, user.organization_id)
    if organization is None:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    return MeRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,  # type: ignore[arg-type]
        organization_id=user.organization_id,
        organization_name=organization.name,
    )
