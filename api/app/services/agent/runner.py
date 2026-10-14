import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import AgentConversation, AgentMessage, AgentToolCall, User
from app.services.agent.dates import now_label
from app.services.agent.llm import (
    AUTH_MESSAGE,
    MODEL_UNAVAILABLE_MESSAGE,
    NOT_CONFIGURED_MESSAGE,
    PROVIDER_MESSAGE,
    RATE_LIMIT_MESSAGE,
    ModelUnavailable,
    ProviderAuth,
    ProviderError,
    RateLimited,
    TurnMessage,
    forget_model,
    plain_text,
    resolve_model,
)
from app.services.agent.providers import build_provider
from app.services.agent.tools import (
    TOOL_SCHEMAS,
    apply_confirmed_status,
    execute_tool,
    prepare_status_change,
    scope_name,
    suggested_answer,
)

logger = logging.getLogger("sentinel.agent")

HISTORY_LIMIT = 10
MAX_ROUNDS = 4
AFFIRM = {"sí", "si", "confirmo", "adelante"}
DENY = {"no", "cancelar", "cancela"}
EMPTY_ANSWER = "No encontré una respuesta. Reformula la pregunta."
FALLBACK = "No pude completar la consulta. Inténtalo de nuevo."


def get_provider():
    return build_provider(settings.llm_provider, settings.llm_api_key)


def read_thread(db: Session, user: User) -> dict:
    conversation = _conversation(db, user, create=False)
    return _payload(db, user, conversation)


def post_message(db: Session, user: User, content: str, site_id: uuid.UUID | None = None) -> dict:
    site = scope_name(db, user, site_id)
    conversation = _conversation(db, user, create=True)
    phrase = _phrase(content)
    pending = conversation.pending_action if isinstance(conversation.pending_action, dict) else None
    if pending and phrase in AFFIRM:
        return _finish(db, user, conversation, content, _confirm_pending(db, user, conversation, pending))
    if pending and phrase in DENY:
        conversation.pending_action = None
        _audit(db, user, conversation, "change_event_status", pending, "rejected", "Cancelada")
        return _finish(db, user, conversation, content, "De acuerdo. No cambié el evento.")
    direct = suggested_answer(db, user, content, site_id)
    if direct is not None:
        return _finish(db, user, conversation, content, direct)
    return _finish(db, user, conversation, content, _answer(db, user, conversation, content, site_id, site))


def reset_conversation(db: Session, user: User) -> dict:
    conversation = _conversation(db, user, create=False)
    if conversation is None:
        return _payload(db, user, None)
    db.execute(
        delete(AgentMessage).where(
            AgentMessage.conversation_id == conversation.id,
            AgentMessage.organization_id == user.organization_id,
        )
    )
    conversation.pending_action = None
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _payload(db, user, conversation)


def confirm_action(db: Session, user: User, action_id: uuid.UUID) -> dict:
    conversation = _conversation(db, user, create=False)
    pending = conversation.pending_action if conversation and isinstance(conversation.pending_action, dict) else None
    if conversation is None or pending is None or pending.get("id") != str(action_id):
        raise LookupError("No hay una acción pendiente de confirmación.")
    text = _confirm_pending(db, user, conversation, pending)
    db.add(
        AgentMessage(
            conversation_id=conversation.id,
            organization_id=user.organization_id,
            role="assistant",
            content=text,
        )
    )
    db.commit()
    return _payload(db, user, conversation)


def cancel_action(db: Session, user: User, action_id: uuid.UUID) -> dict:
    conversation = _conversation(db, user, create=False)
    pending = conversation.pending_action if conversation and isinstance(conversation.pending_action, dict) else None
    if conversation is None or pending is None or pending.get("id") != str(action_id):
        raise LookupError("No hay una acción pendiente de confirmación.")
    conversation.pending_action = None
    _audit(db, user, conversation, "change_event_status", pending, "rejected", "Cancelada")
    db.add(
        AgentMessage(
            conversation_id=conversation.id,
            organization_id=user.organization_id,
            role="assistant",
            content="De acuerdo. No cambié el evento.",
        )
    )
    db.commit()
    return _payload(db, user, conversation)


def _answer(
    db: Session,
    user: User,
    conversation: AgentConversation,
    content: str,
    site_id: uuid.UUID | None,
    site_name: str | None,
) -> str:
    if not settings.llm_api_key:
        return NOT_CONFIGURED_MESSAGE
    try:
        provider = get_provider()
        model = resolve_model(
            provider,
            provider_name=settings.llm_provider,
            api_key=settings.llm_api_key,
            configured=settings.llm_model,
        )
    except ModelUnavailable:
        return MODEL_UNAVAILABLE_MESSAGE
    except RateLimited:
        return RATE_LIMIT_MESSAGE
    except ProviderAuth:
        return AUTH_MESSAGE
    except ProviderError:
        logger.exception("llm model list failed")
        return PROVIDER_MESSAGE
    messages = _history(db, conversation, content)
    try:
        return _rounds(db, user, conversation, provider, model, messages, site_id, site_name)
    except ModelUnavailable:
        forget_model(
            provider_name=settings.llm_provider,
            api_key=settings.llm_api_key,
            configured=settings.llm_model,
        )
        return MODEL_UNAVAILABLE_MESSAGE
    except RateLimited:
        return RATE_LIMIT_MESSAGE
    except ProviderAuth:
        return AUTH_MESSAGE
    except ProviderError:
        logger.exception("llm completion failed")
        return PROVIDER_MESSAGE


def _rounds(
    db: Session,
    user: User,
    conversation: AgentConversation,
    provider,
    model: str,
    messages: list[TurnMessage],
    site_id: uuid.UUID | None,
    site_name: str | None,
) -> str:
    system = _system(site_name)
    for _ in range(MAX_ROUNDS):
        turn = provider.complete(model=model, system=system, messages=messages, tools=TOOL_SCHEMAS)
        if not turn.tool_calls:
            return turn.content.strip() or EMPTY_ANSWER
        if any(call.name == "change_event_status" for call in turn.tool_calls):
            return _propose(db, user, conversation, turn.tool_calls, site_id)
        messages.append(TurnMessage(role="assistant", content=turn.content, tool_calls=turn.tool_calls))
        for call in turn.tool_calls:
            result, outcome, detail = execute_tool(call.name, call.arguments, db, user, site_id)
            _audit(db, user, conversation, call.name, call.arguments, outcome, detail)
            messages.append(
                TurnMessage(
                    role="tool",
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=call.id,
                    tool_name=call.name,
                )
            )
    return FALLBACK


def _propose(db: Session, user: User, conversation: AgentConversation, calls: list, site_id: uuid.UUID | None) -> str:
    selected = next(call for call in calls if call.name == "change_event_status")
    for call in calls:
        if call is selected:
            continue
        _audit(db, user, conversation, call.name, call.arguments, "rejected", "Hay una confirmación pendiente")
    result, outcome, detail = prepare_status_change(selected.arguments, db, user, site_id)
    _audit(db, user, conversation, selected.name, selected.arguments, outcome, detail)
    confirmation = result.get("confirmation")
    if confirmation:
        conversation.pending_action = confirmation
        return confirmation["prompt"]
    return str(result.get("error") or "No pude preparar ese cambio.")


def _confirm_pending(db: Session, user: User, conversation: AgentConversation, pending: dict) -> str:
    conversation.pending_action = None
    try:
        event_id = uuid.UUID(str(pending.get("event_id")))
        status = str(pending.get("status"))
    except (TypeError, ValueError):
        _audit(db, user, conversation, "change_event_status", pending, "rejected", "Confirmación inválida")
        return "Esa confirmación ya no es válida."
    text = apply_confirmed_status(db, user, event_id, status)
    outcome = "executed" if text.startswith("Listo.") else "rejected"
    _audit(db, user, conversation, "change_event_status", pending, outcome, text)
    return text


def _finish(db: Session, user: User, conversation: AgentConversation, content: str, answer: str) -> dict:
    answer = plain_text(answer) or EMPTY_ANSWER
    moment = datetime.now(timezone.utc)
    db.add(
        AgentMessage(
            conversation_id=conversation.id,
            organization_id=user.organization_id,
            role="user",
            content=content,
            created_at=moment,
        )
    )
    db.add(
        AgentMessage(
            conversation_id=conversation.id,
            organization_id=user.organization_id,
            role="assistant",
            content=answer,
            created_at=moment + timedelta(milliseconds=1),
        )
    )
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _payload(db, user, conversation)


def _conversation(db: Session, user: User, *, create: bool) -> AgentConversation | None:
    conversation = db.scalar(
        select(AgentConversation).where(
            AgentConversation.user_id == user.id,
            AgentConversation.organization_id == user.organization_id,
        )
    )
    if conversation is None and create:
        conversation = AgentConversation(organization_id=user.organization_id, user_id=user.id)
        db.add(conversation)
        db.flush()
    return conversation


def _history(db: Session, conversation: AgentConversation, content: str) -> list[TurnMessage]:
    rows = list(
        db.scalars(
            select(AgentMessage)
            .where(AgentMessage.conversation_id == conversation.id)
            .order_by(AgentMessage.created_at.desc())
            .limit(HISTORY_LIMIT)
        )
    )
    rows.reverse()
    messages = [TurnMessage(role=row.role, content=row.content) for row in rows]
    messages.append(TurnMessage(role="user", content=content))
    return messages[-HISTORY_LIMIT:]


def _system(site_name: str | None) -> str:
    if site_name:
        scope = (
            f"El alcance de esta consulta es únicamente el sitio {site_name}. "
            "Las herramientas ya filtran ese sitio. No uses datos de otros sitios."
        )
    else:
        scope = "El alcance de esta consulta es todos los sitios de la organización."
    return (
        "Eres Senti, el asistente de seguridad de SentinelAI. Te presentas como Senti. "
        "Respondes solo en español y solo con datos de las herramientas. "
        "Texto plano: no uses asteriscos, Markdown ni negritas. "
        "No inventes cifras ni describas fotos: no tienes acceso a imágenes. "
        "Para intrusiones de esta semana, eventos críticos de ayer, o minutos y costo de este mes, "
        "llama solo a briefing una vez. Para el resto, usa la menor cantidad de herramientas posible. "
        f"La hora actual en America/Guatemala es {now_label()}. "
        "Traduce ayer, esta semana, anoche, hoy y este mes al periodo de la herramienta. "
        "Esta semana empieza el lunes. Anoche va de las 20:00 de ayer a las 06:00 de hoy. "
        "Identifica un evento por tipo, lugar y hora. No muestres identificadores. "
        "change_event_status solo propone el cambio. No digas que ya se aplicó. "
        "No puedes cambiar la tarifa. Si te lo piden, explica que solo un administrador puede hacerlo en Métricas. "
        "Todas las consultas son de la organización de la persona. "
        + scope
    )


def _audit(
    db: Session,
    user: User,
    conversation: AgentConversation,
    tool_name: str,
    arguments: dict,
    outcome: str,
    detail: str,
) -> None:
    stored = arguments if isinstance(arguments, dict) else {}
    db.add(
        AgentToolCall(
            organization_id=user.organization_id,
            user_id=user.id,
            conversation_id=conversation.id,
            tool_name=tool_name[:64],
            arguments=stored,
            outcome=outcome,
            detail=detail[:500],
        )
    )
    logger.info("agent tool org=%s tool=%s outcome=%s", user.organization_id, tool_name, outcome)


def _payload(db: Session, user: User, conversation: AgentConversation | None) -> dict:
    if conversation is None:
        return {"messages": [], "confirmation": None}
    rows = db.scalars(
        select(AgentMessage)
        .where(
            AgentMessage.conversation_id == conversation.id,
            AgentMessage.organization_id == user.organization_id,
        )
        .order_by(AgentMessage.created_at)
    ).all()
    pending = conversation.pending_action if isinstance(conversation.pending_action, dict) else None
    confirmation = None
    if pending and pending.get("id") and pending.get("prompt"):
        confirmation = {"id": pending["id"], "prompt": pending["prompt"]}
    return {
        "messages": [
            {"id": row.id, "role": row.role, "content": row.content, "created_at": row.created_at} for row in rows
        ],
        "confirmation": confirmation,
    }


def _phrase(content: str) -> str:
    return content.strip().casefold().strip(" \t.¡!¿?,")
