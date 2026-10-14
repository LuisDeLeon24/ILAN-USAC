import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.entities import User
from app.schemas.agent import AgentActionIn, AgentMessageIn, AgentThreadRead
from app.services.agent.runner import cancel_action, confirm_action, post_message, read_thread, reset_conversation

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger("sentinel.agent")


@router.get("/messages", response_model=AgentThreadRead)
def list_messages(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return read_thread(db, user)


@router.post("/messages", response_model=AgentThreadRead)
def create_message(
    payload: AgentMessageIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        return post_message(db, user, payload.content, payload.site_id)
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/reset", response_model=AgentThreadRead)
def reset_messages(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    return reset_conversation(db, user)


@router.post("/confirm", response_model=AgentThreadRead)
def confirm_message(
    payload: AgentActionIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        return confirm_action(db, user, payload.id)
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/cancel", response_model=AgentThreadRead)
def cancel_message(
    payload: AgentActionIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        return cancel_action(db, user, payload.id)
    except LookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
