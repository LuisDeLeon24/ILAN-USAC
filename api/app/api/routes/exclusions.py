import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, scoped_get
from app.db.session import get_db
from app.models.entities import Camera, ExclusionArea, User
from app.schemas.exclusions import ExclusionRead, ExclusionWrite

router = APIRouter(tags=["exclusions"])
logger = logging.getLogger("sentinel.api")


def to_read(area: ExclusionArea) -> ExclusionRead:
    return ExclusionRead(
        id=area.id,
        camera_id=area.camera_id,
        polygon=area.polygon,
        created_at=area.created_at,
    )


@router.get("/cameras/{camera_id}/exclusions", response_model=list[ExclusionRead])
def list_exclusions(
    camera_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ExclusionRead]:
    scoped_get(db, Camera, user, camera_id)
    areas = db.scalars(
        select(ExclusionArea)
        .where(ExclusionArea.camera_id == camera_id, ExclusionArea.organization_id == user.organization_id)
        .order_by(ExclusionArea.created_at.desc())
        .limit(50)
    )
    return [to_read(area) for area in areas]


@router.post("/cameras/{camera_id}/exclusions", response_model=ExclusionRead, status_code=201)
def create_exclusion(
    camera_id: uuid.UUID,
    payload: ExclusionWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ExclusionRead:
    scoped_get(db, Camera, user, camera_id)
    area = ExclusionArea(
        organization_id=user.organization_id,
        camera_id=camera_id,
        polygon=payload.polygon,
    )
    db.add(area)
    db.commit()
    db.refresh(area)
    logger.info("exclusion created org=%s camera=%s exclusion=%s", user.organization_id, camera_id, area.id)
    return to_read(area)


@router.patch("/exclusions/{exclusion_id}", response_model=ExclusionRead)
def update_exclusion(
    exclusion_id: uuid.UUID,
    payload: ExclusionWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ExclusionRead:
    area = scoped_get(db, ExclusionArea, user, exclusion_id)
    area.polygon = payload.polygon
    db.commit()
    db.refresh(area)
    return to_read(area)


@router.delete("/exclusions/{exclusion_id}", status_code=204)
def delete_exclusion(
    exclusion_id: uuid.UUID,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    area = scoped_get(db, ExclusionArea, user, exclusion_id)
    db.delete(area)
    db.commit()
    logger.info("exclusion deleted org=%s exclusion=%s", user.organization_id, exclusion_id)
    return Response(status_code=204)
