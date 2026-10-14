import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, scoped_get
from app.core.security import decrypt_secret, encrypt_secret, mask_rtsp
from app.db.session import get_db
from app.models.entities import Camera, Site, User, Zone
from app.core.config import settings
from app.schemas.cameras import CameraCreate, CameraRead, CameraUpdate, LiveTokenRead
from app.services.live_token import issue_live_token
from app.services.storage import get_bytes

router = APIRouter(prefix="/cameras", tags=["cameras"])
logger = logging.getLogger("sentinel.api")
FRAME_TTL = timedelta(minutes=10)


def masked_url(camera: Camera) -> str | None:
    if not camera.rtsp_url_encrypted:
        return None
    try:
        return mask_rtsp(decrypt_secret(camera.rtsp_url_encrypted))
    except Exception:
        logger.exception("failed to decrypt rtsp url for camera %s", camera.id)
        return None


def to_read(camera: Camera, zone_count: int) -> CameraRead:
    return CameraRead(
        id=camera.id,
        site_id=camera.site_id,
        name=camera.name,
        source_type=camera.source_type,  # type: ignore[arg-type]
        rtsp_url_masked=masked_url(camera),
        file_path=camera.file_path,
        fps=camera.fps,
        enabled=camera.enabled,
        loop=camera.loop,
        min_confidence=float(camera.min_confidence),
        min_box_area=float(camera.min_box_area),
        zone_count=zone_count,
        created_at=camera.created_at,
    )


def zone_counts(db: Session, user: User) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(Zone.camera_id, func.count(Zone.id))
        .where(Zone.organization_id == user.organization_id)
        .group_by(Zone.camera_id)
    ).all()
    return {camera_id: count for camera_id, count in rows}


def ensure_source(camera: Camera) -> None:
    if camera.source_type == "rtsp":
        if not camera.rtsp_url_encrypted:
            raise HTTPException(status_code=422, detail="La URL debe comenzar con rtsp://")
        camera.file_path = None
        camera.loop = False
        return
    if camera.source_type == "file":
        if not camera.file_path:
            raise HTTPException(status_code=422, detail="Indica la ruta del archivo")
        camera.rtsp_url_encrypted = None
        return
    raise HTTPException(status_code=422, detail="Tipo de fuente no válido")


@router.get("", response_model=list[CameraRead])
def list_cameras(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    site_id: uuid.UUID | None = None,
) -> list[CameraRead]:
    query = select(Camera).where(Camera.organization_id == user.organization_id)
    if site_id is not None:
        scoped_get(db, Site, user, site_id)
        query = query.where(Camera.site_id == site_id)
    cameras = list(db.scalars(query.order_by(Camera.created_at.desc()).limit(200)))
    counts = zone_counts(db, user)
    return [to_read(camera, counts.get(camera.id, 0)) for camera in cameras]


@router.get("/{camera_id}", response_model=CameraRead)
def get_camera(
    camera_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraRead:
    camera = scoped_get(db, Camera, user, camera_id)
    count = db.scalar(select(func.count()).select_from(Zone).where(Zone.camera_id == camera.id)) or 0
    return to_read(camera, count)


@router.post("", response_model=CameraRead, status_code=201)
def create_camera(
    payload: CameraCreate,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraRead:
    scoped_get(db, Site, user, payload.site_id)
    camera = Camera(
        organization_id=user.organization_id,
        site_id=payload.site_id,
        name=payload.name,
        source_type=payload.source_type,
        file_path=payload.file_path,
        fps=payload.fps,
        enabled=payload.enabled,
        loop=payload.loop,
        min_confidence=payload.min_confidence,
        min_box_area=payload.min_box_area,
        rtsp_url_encrypted=encrypt_secret(payload.rtsp_url) if payload.rtsp_url else None,
    )
    ensure_source(camera)
    db.add(camera)
    db.commit()
    db.refresh(camera)
    logger.info("camera created org=%s camera=%s source=%s", user.organization_id, camera.id, camera.source_type)
    return to_read(camera, 0)


@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(
    camera_id: uuid.UUID,
    payload: CameraUpdate,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> CameraRead:
    camera = scoped_get(db, Camera, user, camera_id)
    changes = payload.model_dump(exclude_unset=True)
    if "site_id" in changes and changes["site_id"] is not None:
        scoped_get(db, Site, user, changes["site_id"])
        camera.site_id = changes["site_id"]
    if "name" in changes and changes["name"] is not None:
        camera.name = changes["name"]
    if "fps" in changes and changes["fps"] is not None:
        camera.fps = changes["fps"]
    if "enabled" in changes and changes["enabled"] is not None:
        camera.enabled = changes["enabled"]
    if "loop" in changes and changes["loop"] is not None:
        camera.loop = changes["loop"]
    if "min_confidence" in changes and changes["min_confidence"] is not None:
        camera.min_confidence = changes["min_confidence"]
    if "min_box_area" in changes and changes["min_box_area"] is not None:
        camera.min_box_area = changes["min_box_area"]
    if "source_type" in changes and changes["source_type"] is not None:
        camera.source_type = changes["source_type"]
    if "file_path" in changes:
        camera.file_path = changes["file_path"]
    if changes.get("rtsp_url"):
        camera.rtsp_url_encrypted = encrypt_secret(changes["rtsp_url"])
    ensure_source(camera)
    db.commit()
    db.refresh(camera)
    count = db.scalar(select(func.count()).select_from(Zone).where(Zone.camera_id == camera.id)) or 0
    return to_read(camera, count)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: uuid.UUID,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    camera = scoped_get(db, Camera, user, camera_id)
    db.delete(camera)
    db.commit()
    logger.info("camera deleted org=%s camera=%s", user.organization_id, camera_id)
    return Response(status_code=204)


def frame_is_current(camera: Camera, moment: datetime | None = None) -> bool:
    if not camera.preview_key or camera.preview_at is None or camera.frame_requested:
        return False
    now = moment or datetime.now(timezone.utc)
    return now - camera.preview_at <= FRAME_TTL


@router.post("/{camera_id}/frame-request")
def request_frame(
    camera_id: uuid.UUID,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, bool]:
    camera = scoped_get(db, Camera, user, camera_id)
    camera.frame_requested = True
    db.commit()
    logger.info("frame requested org=%s camera=%s", user.organization_id, camera.id)
    return {"frame_requested": True}


@router.get("/{camera_id}/frame")
def camera_frame(
    camera_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    camera = scoped_get(db, Camera, user, camera_id)
    if not frame_is_current(camera) or camera.preview_key is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return Response(content=get_bytes(camera.preview_key), media_type="image/jpeg")


@router.post("/{camera_id}/live-token", response_model=LiveTokenRead)
def live_token(
    camera_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> LiveTokenRead:
    camera = scoped_get(db, Camera, user, camera_id)
    if not settings.live_stream_secret or not settings.worker_public_url:
        raise HTTPException(status_code=503, detail="La vista en vivo no está configurada")
    token, expires = issue_live_token(settings.live_stream_secret, user.organization_id, camera.id)
    base = settings.worker_public_url
    logger.info("live token org=%s camera=%s", user.organization_id, camera.id)
    return LiveTokenRead(
        token=token,
        expires_at=datetime.fromtimestamp(expires, timezone.utc),
        stream_url=f"{base}/live/{camera.id}.mjpg",
        status_url=f"{base}/live/{camera.id}/status",
    )
