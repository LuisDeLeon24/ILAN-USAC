import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Event
from app.services.alerts import read_snapshot_token
from app.services.storage import get_bytes

router = APIRouter(tags=["public"])
logger = logging.getLogger("sentinel.api")


@router.get("/public/snapshots/{token}")
def public_snapshot(token: str, db: Annotated[Session, Depends(get_db)]) -> Response:
    event_id = read_snapshot_token(token)
    if event_id is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    event = db.get(Event, event_id)
    if event is None or not event.snapshot_key:
        raise HTTPException(status_code=404, detail="No encontrado")
    try:
        payload = get_bytes(event.snapshot_key)
    except Exception:
        logger.exception("public snapshot missing event=%s", event.id)
        raise HTTPException(status_code=404, detail="No encontrado") from None
    return Response(content=payload, media_type="image/jpeg")
