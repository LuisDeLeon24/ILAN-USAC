"""Alerts. WhatsApp uses Twilio or the console. Telegram uses the Bot API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_TIMEZONE, settings
from app.db.session import SessionLocal
from app.models.entities import AlertContact, AlertLog, Camera, Event, Organization, Sensor, Site
from app.services.storage import get_bytes

logger = logging.getLogger("sentinel.api")

SNAPSHOT_TTL_SECONDS = 3600
DETAIL_LIMIT = 500
ALERT_SEVERITIES = {"medium", "high", "critical"}
NO_CONTACTS = "No hay contactos activos"
COOLED = "Enfriamiento de alertas"
_MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
TYPE_LABELS = {
    "intrusion": "Intrusión",
    "after_hours": "Fuera de horario",
    "loitering": "Merodeo",
    "occupancy": "Ocupación",
    "camera_disconnected": "Cámara desconectada",
    "door_open": "Puerta abierta",
    "motion": "Movimiento",
    "smoke": "Humo",
    "panic": "Botón de pánico",
}
SEVERITY_LABELS = {
    "low": "Baja",
    "medium": "Media",
    "high": "Alta",
    "critical": "Crítico",
}


class AlertDeliveryError(Exception):
    def __init__(self, reason: str, twilio_code: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.twilio_code = twilio_code


class ConsoleProvider:
    name = "console"

    def send(self, phone: str, body: str, media_url: str | None) -> None:
        logger.info("alert console to=%s media=%s\n%s", phone, media_url or "-", body)


# Twilio asks for a template when the 24-hour session is closed (63016) or the
# request is rejected as ContentSid Required (21654, 92005).
_TEMPLATE_CODES = {21654, 63016, 92005}


class TwilioProvider:
    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, sender: str, content_sid: str = "") -> None:
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.sender = _whatsapp_address(sender)
        self.content_sid = content_sid.strip()

    def send(self, phone: str, body: str, media_url: str | None) -> None:
        fields = {"From": self.sender, "To": _whatsapp_address(phone), "Body": body}
        if media_url:
            fields["MediaUrl"] = media_url
        try:
            self._post(fields)
        except AlertDeliveryError as exc:
            if not self.content_sid or not _needs_content_template(exc):
                raise
            logger.info("twilio free-form rejected code=%s; retrying with ContentSid", exc.twilio_code)
            self._post({"From": self.sender, "To": _whatsapp_address(phone), "ContentSid": self.content_sid})

    def _post(self, fields: dict[str, str]) -> None:
        names = _parameter_names(fields)
        logger.info("twilio request parameters=%s", names)
        payload = urllib.parse.urlencode(fields).encode()
        request = urllib.request.Request(
            f"https://api.twilio.com/2010-04-01/Accounts/{urllib.parse.quote(self.account_sid, safe='')}/Messages.json",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status not in (200, 201):
                    raise AlertDeliveryError(f"Twilio respondió {response.status}. Parámetros: {names}")
        except AlertDeliveryError:
            raise
        except urllib.error.HTTPError as exc:
            raise _twilio_failure(exc, names) from None
        except urllib.error.URLError:
            raise AlertDeliveryError(f"Twilio no respondió. Parámetros: {names}") from None


def get_provider() -> ConsoleProvider | TwilioProvider:
    sid = settings.twilio_account_sid
    token = settings.twilio_auth_token
    sender = settings.twilio_whatsapp_from
    filled = (bool(sid), bool(token), bool(sender))
    if any(filled) and not all(filled):
        logger.warning("Twilio WhatsApp config is incomplete; using ConsoleProvider")
        return ConsoleProvider()
    if all(filled):
        return TwilioProvider(sid, token, sender, settings.twilio_content_sid)
    return ConsoleProvider()


CAPTION_LIMIT = 1024


@dataclass(frozen=True)
class StartedChat:
    chat_id: str
    label: str
    username: str | None


class TelegramProvider:
    name = "telegram"

    def __init__(self, token: str) -> None:
        self.token = token

    def send(self, chat_id: str, body: str, photo: bytes | None) -> None:
        if photo:
            payload, content_type = _encode_photo(chat_id, body, photo)
            _telegram_request(self.token, "sendPhoto", payload, content_type)
            return
        payload = json.dumps({"chat_id": chat_id, "text": body}, ensure_ascii=False).encode()
        _telegram_request(self.token, "sendMessage", payload, "application/json")


def list_started_chats() -> list[StartedChat]:
    token = settings.telegram_bot_token
    if not token:
        raise AlertDeliveryError("Telegram no está configurado")
    # No offset: confirming updates would hide /start before the admin links the chat.
    payload = json.dumps({"timeout": 0, "allowed_updates": ["message"]}).encode()
    response = _telegram_request(token, "getUpdates", payload, "application/json")
    result = response.get("result")
    if not isinstance(result, list):
        raise AlertDeliveryError("Telegram no devolvió la lista de chats")
    return _chats_from_updates(result)


def snapshot_token(event_id: uuid.UUID, expires: int) -> str:
    signature = _sign(event_id, expires)
    return f"{event_id}.{expires}.{signature}"


def read_snapshot_token(token: str) -> uuid.UUID | None:
    event_id_text, separator, rest = token.partition(".")
    expires_text, dot, signature = rest.partition(".")
    if not separator or not dot or not signature:
        return None
    try:
        event_id = uuid.UUID(event_id_text)
        expires = int(expires_text)
    except ValueError:
        return None
    if expires < int(time.time()):
        return None
    expected = _sign(event_id, expires)
    if not hmac.compare_digest(expected, signature):
        return None
    return event_id


def dispatch_event_alerts(event_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        event = db.get(Event, event_id)
        if event is None or event.severity not in ALERT_SEVERITIES:
            return
        _deliver(db, event.organization_id, event=event, is_test=False)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("alert dispatch failed event=%s", event_id)
    finally:
        db.close()


def send_test_alert(db: Session, organization_id: uuid.UUID) -> str:
    logs = _deliver(db, organization_id, event=None, is_test=True)
    db.commit()
    if not logs:
        return NO_CONTACTS
    if all(row.status == "sent" for row in logs):
        return "Alerta de prueba enviada"
    if any(row.status == "sent" for row in logs):
        return "Algunos envíos fallaron"
    if len(logs) == 1 and logs[0].detail == NO_CONTACTS:
        return NO_CONTACTS
    return "No se pudo enviar la alerta de prueba"


def _deliver(db: Session, organization_id: uuid.UUID, event: Event | None, is_test: bool) -> list[AlertLog]:
    whatsapp = get_provider()
    if event is not None and event.severity != "critical" and _cooled(db, event):
        provider_name = _suppressed_provider(db, organization_id)
        row = _log(
            db,
            organization_id=organization_id,
            event_id=event.id,
            contact_id=None,
            provider=provider_name,
            status="suppressed",
            detail=COOLED,
            is_test=False,
            sent_at=None,
        )
        logger.info("alert suppressed org=%s event=%s key=%s", organization_id, event.id, event.cooldown_key)
        return [row]
    contacts = list(
        db.scalars(
            select(AlertContact)
            .where(AlertContact.organization_id == organization_id, AlertContact.enabled.is_(True))
            .order_by(AlertContact.created_at.asc())
        )
    )
    body, media_url = _message(db, organization_id, event, is_test)
    if not contacts:
        row = _log(
            db,
            organization_id=organization_id,
            event_id=None if event is None else event.id,
            contact_id=None,
            provider=whatsapp.name,
            status="failed",
            detail=NO_CONTACTS,
            is_test=is_test,
            sent_at=None,
        )
        return [row]
    photo, photo_error = _telegram_photo(event, contacts)
    rows: list[AlertLog] = []
    for contact in contacts:
        provider_name = "telegram" if contact.channel == "telegram" else whatsapp.name
        try:
            if contact.channel == "telegram":
                if photo_error is not None:
                    raise photo_error
                if not contact.chat_id:
                    raise AlertDeliveryError("El contacto no tiene un chat de Telegram")
                _send_telegram(contact.chat_id, body, photo)
            else:
                if not contact.phone:
                    raise AlertDeliveryError("El contacto no tiene número de WhatsApp")
                whatsapp.send(contact.phone, body, media_url)
        except AlertDeliveryError as exc:
            rows.append(
                _log(
                    db,
                    organization_id=organization_id,
                    event_id=None if event is None else event.id,
                    contact_id=contact.id,
                    provider=provider_name,
                    status="failed",
                    detail=exc.reason,
                    is_test=is_test,
                    sent_at=None,
                )
            )
            logger.info("alert failed org=%s contact=%s provider=%s", organization_id, contact.id, provider_name)
            continue
        sent_at = datetime.now(timezone.utc)
        rows.append(
            _log(
                db,
                organization_id=organization_id,
                event_id=None if event is None else event.id,
                contact_id=contact.id,
                provider=provider_name,
                status="sent",
                detail=None,
                is_test=is_test,
                sent_at=sent_at,
            )
        )
        logger.info("alert sent org=%s contact=%s provider=%s test=%s", organization_id, contact.id, provider_name, is_test)
    return rows


def _suppressed_provider(db: Session, organization_id: uuid.UUID) -> str:
    channels = set(
        db.scalars(
            select(AlertContact.channel).where(
                AlertContact.organization_id == organization_id,
                AlertContact.enabled.is_(True),
            )
        )
    )
    if channels == {"telegram"}:
        return "telegram"
    return get_provider().name


def _telegram_photo(event: Event | None, contacts: list[AlertContact]) -> tuple[bytes | None, AlertDeliveryError | None]:
    if event is None or not event.snapshot_key or not any(contact.channel == "telegram" for contact in contacts):
        return None, None
    try:
        return get_bytes(event.snapshot_key), None
    except Exception:
        logger.exception("alert snapshot unreadable event=%s", event.id)
        return None, AlertDeliveryError("No se pudo leer la imagen del evento")


def _send_telegram(chat_id: str, body: str, photo: bytes | None) -> None:
    token = settings.telegram_bot_token
    if not token:
        raise AlertDeliveryError("Telegram no está configurado")
    TelegramProvider(token).send(chat_id, body, photo)


def _cooled(db: Session, event: Event) -> bool:
    if not event.cooldown_key:
        return False
    window = datetime.now(timezone.utc) - timedelta(seconds=settings.alert_cooldown_seconds)
    last = db.scalar(
        select(AlertLog.id)
        .join(Event, Event.id == AlertLog.event_id)
        .where(
            Event.organization_id == event.organization_id,
            Event.cooldown_key == event.cooldown_key,
            Event.id != event.id,
            AlertLog.status == "sent",
            AlertLog.is_test.is_(False),
            AlertLog.sent_at.is_not(None),
            AlertLog.sent_at >= window,
        )
        .limit(1)
    )
    return last is not None


def _message(db: Session, organization_id: uuid.UUID, event: Event | None, is_test: bool) -> tuple[str, str | None]:
    zone_name = _timezone_name(db, organization_id)
    if is_test or event is None:
        moment = datetime.now(timezone.utc)
        lines = [
            "SentinelAI",
            "Tipo: Prueba de alerta",
            "Severidad: Media",
            "Origen: Prueba",
            f"Hora: {format_local(moment, zone_name)}",
        ]
        return "\n".join(lines), None
    camera_name, sensor_name, site_name = _names(db, event)
    lines = [
        "SentinelAI",
        f"Tipo: {TYPE_LABELS.get(event.event_type, event.event_type)}",
        f"Severidad: {SEVERITY_LABELS.get(event.severity, event.severity)}",
    ]
    if sensor_name:
        lines.append(f"Sensor: {sensor_name}")
    elif camera_name:
        lines.append(f"Cámara: {camera_name}")
    if site_name:
        lines.append(f"Sitio: {site_name}")
    lines.append(f"Hora: {format_local(event.occurred_at, zone_name)}")
    return "\n".join(lines), _media_url(event)


def _names(db: Session, event: Event) -> tuple[str | None, str | None, str | None]:
    camera_name = None
    sensor_name = None
    site_name = None
    if event.camera_id is not None:
        camera = db.get(Camera, event.camera_id)
        if camera is not None and camera.organization_id == event.organization_id:
            camera_name = camera.name
            site = db.get(Site, camera.site_id)
            if site is not None:
                site_name = site.name
    if event.sensor_id is not None:
        sensor = db.get(Sensor, event.sensor_id)
        if sensor is not None and sensor.organization_id == event.organization_id:
            sensor_name = sensor.name
            site = db.get(Site, sensor.site_id)
            if site is not None:
                site_name = site.name
    return camera_name, sensor_name, site_name


def _media_url(event: Event) -> str | None:
    base = settings.public_base_url
    if not base or not event.snapshot_key:
        return None
    expires = int(time.time()) + SNAPSHOT_TTL_SECONDS
    return f"{base}/public/snapshots/{snapshot_token(event.id, expires)}"


def _timezone_name(db: Session, organization_id: uuid.UUID) -> str:
    organization = db.get(Organization, organization_id)
    if organization is None or not organization.timezone:
        return DEFAULT_TIMEZONE
    try:
        ZoneInfo(organization.timezone)
    except Exception:
        return DEFAULT_TIMEZONE
    return organization.timezone


def format_local(moment: datetime, timezone_name: str) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(ZoneInfo(timezone_name))
    return f"{local.day:02d} {_MONTHS[local.month - 1]} {local.year}, {local:%H:%M}"


def _log(
    db: Session,
    organization_id: uuid.UUID,
    event_id: uuid.UUID | None,
    contact_id: uuid.UUID | None,
    provider: str,
    status: str,
    detail: str | None,
    is_test: bool,
    sent_at: datetime | None,
) -> AlertLog:
    row = AlertLog(
        organization_id=organization_id,
        event_id=event_id,
        alert_contact_id=contact_id,
        provider=provider,
        status=status,
        detail=_clip(detail),
        is_test=is_test,
        sent_at=sent_at,
    )
    db.add(row)
    db.flush()
    return row


def _sign(event_id: uuid.UUID, expires: int) -> str:
    message = f"{event_id}:{expires}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()


def _clip(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) <= DETAIL_LIMIT:
        return cleaned
    return cleaned[:DETAIL_LIMIT]


def _whatsapp_address(value: str) -> str:
    cleaned = value.strip()
    if cleaned.lower().startswith("whatsapp:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    return f"whatsapp:{cleaned}"


def _parameter_names(fields: dict[str, str]) -> str:
    return ", ".join(fields)


def _encode_photo(chat_id: str, body: str, photo: bytes) -> tuple[bytes, str]:
    caption = body if len(body) <= CAPTION_LIMIT else body[:CAPTION_LIMIT]
    boundary = f"sentinel{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in (("chat_id", chat_id), ("caption", caption)):
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n'
                f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            ).encode()
            + value.encode("utf-8")
            + b"\r\n"
        )
    chunks.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="event.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode()
        + photo
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _telegram_request(token: str, method: str, payload: bytes, content_type: str) -> dict:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=payload,
        method="POST",
        headers={"Content-Type": content_type},
    )
    logger.info("telegram request method=%s", method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        _telegram_payload(exc.read(), token, exc.code)
        raise AlertDeliveryError(_telegram_reason(exc.code, "", token)) from None
    except urllib.error.URLError:
        raise AlertDeliveryError("Telegram no respondió") from None
    if status not in (200, 201):
        raise AlertDeliveryError(_telegram_reason(status, "", token))
    return _telegram_payload(raw, token, status)


def _telegram_payload(raw: bytes, token: str, http_status: int) -> dict:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AlertDeliveryError(_telegram_reason(http_status, "", token)) from None
    if not isinstance(payload, dict):
        raise AlertDeliveryError(_telegram_reason(http_status, "", token))
    if payload.get("ok") is True:
        return payload
    code = payload.get("error_code")
    if not isinstance(code, int):
        code = http_status if http_status >= 400 else None
    description = payload.get("description")
    text = description.strip() if isinstance(description, str) else ""
    raise AlertDeliveryError(_telegram_reason(code, text, token))


def _telegram_reason(code: int | None, description: str, token: str) -> str:
    description = _redact(description, token)
    if code is not None and description:
        reason = f"Telegram {code}: {description}"
    elif description:
        reason = f"Telegram: {description}"
    elif code is not None:
        reason = f"Telegram respondió {code}"
    else:
        reason = "Telegram no aceptó el mensaje"
    return _clip(reason) or reason


def _redact(value: str, token: str) -> str:
    if token and token in value:
        return value.replace(token, "[token]")
    return value


def _is_start(text: str) -> bool:
    command = text.strip().split(maxsplit=1)[0]
    return command.split("@", 1)[0] == "/start"


def _chat_label(chat: dict) -> str:
    first = chat.get("first_name") if isinstance(chat.get("first_name"), str) else ""
    last = chat.get("last_name") if isinstance(chat.get("last_name"), str) else ""
    name = " ".join(part.strip() for part in (first, last) if part.strip())
    if name:
        return name[:200]
    title = chat.get("title") if isinstance(chat.get("title"), str) else ""
    if title.strip():
        return title.strip()[:200]
    username = chat.get("username") if isinstance(chat.get("username"), str) else ""
    if username.strip():
        return username.strip()[:200]
    return "Chat de Telegram"


def _chats_from_updates(updates: list) -> list[StartedChat]:
    ranked: list[tuple[int, str, str, str | None]] = []
    for update in updates:
        if not isinstance(update, dict):
            continue
        message = update.get("message")
        if not isinstance(message, dict):
            continue
        text = message.get("text")
        if not isinstance(text, str) or not _is_start(text):
            continue
        chat = message.get("chat")
        if not isinstance(chat, dict):
            continue
        raw_id = chat.get("id")
        if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id == 0:
            continue
        username = chat.get("username")
        clean_username = username.strip() if isinstance(username, str) and username.strip() else None
        moment = message.get("date")
        ranked.append((moment if isinstance(moment, int) else 0, str(raw_id), _chat_label(chat), clean_username))
    ranked.sort(key=lambda item: item[0], reverse=True)
    chosen: list[StartedChat] = []
    seen: set[str] = set()
    for _moment, chat_id, label, username in ranked:
        if chat_id in seen:
            continue
        seen.add(chat_id)
        chosen.append(StartedChat(chat_id=chat_id, label=label, username=username))
        if len(chosen) == 20:
            break
    return chosen


def _needs_content_template(exc: AlertDeliveryError) -> bool:
    if exc.twilio_code in _TEMPLATE_CODES:
        return True
    text = exc.reason.lower()
    return "contentsid required" in text or "message template" in text or "outside the allowed window" in text


def _twilio_failure(exc: urllib.error.HTTPError, names: str) -> AlertDeliveryError:
    raw = exc.read().decode("utf-8", errors="replace")
    code: int | None = None
    message = ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        parsed = payload.get("code")
        if isinstance(parsed, int):
            code = parsed
        elif isinstance(parsed, str) and parsed.isdigit():
            code = int(parsed)
        message = str(payload.get("message") or "").strip()
    if code is not None and message:
        reason = f"Twilio {code}: {message}. Parámetros: {names}"
    elif message:
        reason = f"Twilio: {message}. Parámetros: {names}"
    else:
        reason = f"Twilio respondió {exc.code}. Parámetros: {names}"
    clipped = _clip(reason) or reason
    return AlertDeliveryError(clipped, twilio_code=code)
