import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin, scoped_get
from app.db.session import get_db
from app.models.entities import AlertContact, AlertLog, Event, User
from app.schemas.alerts import AlertContactRead, AlertContactWrite, AlertLogRead, TelegramChatRead, TestAlertResult
from app.services.alerts import AlertDeliveryError, list_started_chats, send_test_alert

router = APIRouter(prefix="/alerts", tags=["alerts"])
logger = logging.getLogger("sentinel.api")
LOG_LIMIT = 50


def _contact(row: AlertContact) -> AlertContactRead:
    return AlertContactRead(
        id=row.id,
        name=row.name,
        channel=row.channel,  # type: ignore[arg-type]
        phone=row.phone,
        chat_id=row.chat_id,
        enabled=row.enabled,
        created_at=row.created_at,
    )


def _apply(row: AlertContact, payload: AlertContactWrite) -> None:
    row.name = payload.name
    row.channel = payload.channel
    row.phone = payload.phone
    row.chat_id = payload.chat_id
    row.enabled = payload.enabled


def _chat_taken(db: Session, user: User, chat_id: str, ignore_id: uuid.UUID | None = None) -> bool:
    existing = db.scalar(
        select(AlertContact).where(AlertContact.organization_id == user.organization_id, AlertContact.chat_id == chat_id)
    )
    return existing is not None and existing.id != ignore_id


@router.get("/contacts", response_model=list[AlertContactRead])
def list_contacts(
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AlertContactRead]:
    rows = db.scalars(
        select(AlertContact)
        .where(AlertContact.organization_id == user.organization_id)
        .order_by(AlertContact.created_at.desc())
        .limit(200)
    )
    return [_contact(row) for row in rows]


@router.post("/contacts", response_model=AlertContactRead, status_code=201)
def create_contact(
    payload: AlertContactWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertContactRead:
    if payload.chat_id and _chat_taken(db, user, payload.chat_id):
        raise HTTPException(status_code=409, detail="Ese chat de Telegram ya está vinculado")
    row = AlertContact(organization_id=user.organization_id)
    _apply(row, payload)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ese chat de Telegram ya está vinculado") from None
    db.refresh(row)
    logger.info("alert contact created org=%s contact=%s channel=%s", user.organization_id, row.id, row.channel)
    return _contact(row)


@router.patch("/contacts/{contact_id}", response_model=AlertContactRead)
def update_contact(
    contact_id: uuid.UUID,
    payload: AlertContactWrite,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AlertContactRead:
    row = scoped_get(db, AlertContact, user, contact_id)
    if payload.chat_id and _chat_taken(db, user, payload.chat_id, ignore_id=row.id):
        raise HTTPException(status_code=409, detail="Ese chat de Telegram ya está vinculado")
    _apply(row, payload)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ese chat de Telegram ya está vinculado") from None
    db.refresh(row)
    return _contact(row)


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(
    contact_id: uuid.UUID,
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    row = scoped_get(db, AlertContact, user, contact_id)
    db.delete(row)
    db.commit()
    logger.info("alert contact deleted org=%s contact=%s", user.organization_id, contact_id)
    return Response(status_code=204)


@router.get("/logs", response_model=list[AlertLogRead])
def list_logs(
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AlertLogRead]:
    rows = db.execute(
        select(AlertLog, AlertContact.name, Event.event_type)
        .outerjoin(AlertContact, AlertContact.id == AlertLog.alert_contact_id)
        .outerjoin(Event, Event.id == AlertLog.event_id)
        .where(AlertLog.organization_id == user.organization_id)
        .order_by(AlertLog.created_at.desc())
        .limit(LOG_LIMIT)
    ).all()
    return [
        AlertLogRead(
            id=log.id,
            event_id=log.event_id,
            event_type=event_type,
            contact_name=contact_name,
            provider=log.provider,
            status=log.status,  # type: ignore[arg-type]
            detail=log.detail,
            is_test=log.is_test,
            created_at=log.created_at,
        )
        for log, contact_name, event_type in rows
    ]


@router.get("/telegram/chats", response_model=list[TelegramChatRead])
def list_telegram_chats(user: Annotated[User, Depends(require_admin)]) -> list[TelegramChatRead]:
    try:
        chats = list_started_chats()
    except AlertDeliveryError as exc:
        raise HTTPException(status_code=503, detail=exc.reason) from None
    logger.info("telegram chats listed org=%s count=%s", user.organization_id, len(chats))
    return [TelegramChatRead(chat_id=chat.chat_id, label=chat.label, username=chat.username) for chat in chats]


@router.post("/test", response_model=TestAlertResult)
def test_alert(
    user: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> TestAlertResult:
    message = send_test_alert(db, user.organization_id)
    logger.info("alert test org=%s", user.organization_id)
    return TestAlertResult(message=message)
