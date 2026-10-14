import io
import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from http.client import HTTPMessage

from app.core.config import settings
from app.services.alerts import AlertDeliveryError, TelegramProvider, TwilioProvider, get_provider, snapshot_token
from tests.conftest import auth_header
from tests.test_device import JPEG, device_headers, open_site


class RecordingProvider:
    name = "console"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str | None]] = []

    def send(self, phone: str, body: str, media_url: str | None) -> None:
        self.sent.append((phone, body, media_url))


class FailingProvider:
    name = "twilio"

    def send(self, phone: str, body: str, media_url: str | None) -> None:
        raise AlertDeliveryError("Twilio: sandbox")


def _use(monkeypatch, provider) -> None:
    monkeypatch.setattr("app.services.alerts.get_provider", lambda: provider)


def _contact(client, headers, phone="+50255555555", enabled=True, name="Operador"):
    response = client.post(
        "/alerts/contacts",
        json={"name": name, "phone": phone, "enabled": enabled},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _sensor(client, headers, site_id, sensor_type="door", external_id="puerta-bodega", name="Puerta bodega"):
    response = client.post(
        "/sensors",
        json={"site_id": site_id, "name": name, "sensor_type": sensor_type, "external_id": external_id},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _sensor_event(client, token, sensor_id, event_type, when: datetime):
    return client.post(
        "/device/sensor-events",
        json={
            "client_event_id": str(uuid.uuid4()),
            "sensor_id": sensor_id,
            "event_type": event_type,
            "occurred_at": when.isoformat(),
        },
        headers=device_headers(token),
    )


def _camera_event(client, token, camera_id, zone_id, when: datetime, event_type="intrusion", snapshot=False):
    meta = {
        "client_event_id": str(uuid.uuid4()),
        "camera_id": camera_id,
        "zone_id": zone_id,
        "event_type": event_type,
        "occurred_at": when.isoformat(),
    }
    files = {"snapshot": ("snap.jpg", JPEG, "image/jpeg")} if snapshot else None
    return client.post("/device/events", data={"meta": json.dumps(meta)}, files=files, headers=device_headers(token))


class _OpenResponse:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _capture_urlopen(monkeypatch):
    calls: list[urllib.request.Request] = []

    def fake_urlopen(request, timeout=15):
        assert timeout == 15
        calls.append(request)
        return _OpenResponse()

    monkeypatch.setattr("app.services.alerts.urllib.request.urlopen", fake_urlopen)
    return calls


def _form(request: urllib.request.Request) -> dict[str, list[str]]:
    assert request.data is not None
    assert not request.data.startswith(b"{")
    assert request.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert "Messages.json" in request.full_url
    return urllib.parse.parse_qs(request.data.decode(), keep_blank_values=True)


def _twilio_http_error(request: urllib.request.Request, payload: dict) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        request.full_url,
        400,
        "Bad Request",
        HTTPMessage(),
        io.BytesIO(json.dumps(payload).encode()),
    )


def test_twilio_posts_urlencoded_form_fields(monkeypatch) -> None:
    calls = _capture_urlopen(monkeypatch)
    TwilioProvider("AC123", "secret-token", "whatsapp:+17370000000").send(
        "+50255555555",
        "Tipo: Intrusión\nSeveridad: Alta",
        None,
    )
    assert len(calls) == 1
    parsed = _form(calls[0])
    assert list(parsed) == ["From", "To", "Body"]
    assert parsed["From"] == ["whatsapp:+17370000000"]
    assert parsed["To"] == ["whatsapp:+50255555555"]
    assert parsed["Body"] == ["Tipo: Intrusión\nSeveridad: Alta"]
    assert "ContentSid" not in parsed
    assert "ContentVariables" not in parsed


def test_twilio_error_records_code_message_and_parameter_names(monkeypatch) -> None:
    def fake_urlopen(request, timeout=15):
        raise _twilio_http_error(request, {"code": 21654, "message": "ContentSid Required", "status": 400})

    monkeypatch.setattr("app.services.alerts.urllib.request.urlopen", fake_urlopen)
    provider = TwilioProvider("AC123", "secret-token", "+17370000000")
    try:
        provider.send("+50255555555", "Tipo: Prueba de alerta", None)
    except AlertDeliveryError as exc:
        reason = exc.reason
        code = exc.twilio_code
    else:
        raise AssertionError("expected Twilio failure")
    assert code == 21654
    assert reason == "Twilio 21654: ContentSid Required. Parámetros: From, To, Body"
    assert "+50255555555" not in reason
    assert "secret-token" not in reason
    assert "Prueba de alerta" not in reason


def test_content_sid_is_sent_only_after_twilio_requires_it(monkeypatch) -> None:
    calls: list[urllib.request.Request] = []

    def fake_urlopen(request, timeout=15):
        calls.append(request)
        parsed = urllib.parse.parse_qs(request.data.decode())
        if "Body" in parsed:
            raise _twilio_http_error(request, {"code": 63016, "message": "Failed to send freeform message because you are outside the allowed window", "status": 400})
        return _OpenResponse()

    monkeypatch.setattr("app.services.alerts.urllib.request.urlopen", fake_urlopen)
    TwilioProvider("AC123", "secret-token", "+17370000000", content_sid="HXtemplate").send(
        "+50255555555",
        "Tipo: Prueba de alerta",
        "https://alerts.example/public/snapshots/token",
    )
    assert len(calls) == 2
    first = _form(calls[0])
    second = _form(calls[1])
    assert list(first) == ["From", "To", "Body", "MediaUrl"]
    assert list(second) == ["From", "To", "ContentSid"]
    assert second["ContentSid"] == ["HXtemplate"]
    assert "Body" not in second
    assert "MediaUrl" not in second
    assert "ContentVariables" not in second


def test_content_sid_stays_unused_for_other_twilio_errors(monkeypatch) -> None:
    calls: list[urllib.request.Request] = []

    def fake_urlopen(request, timeout=15):
        calls.append(request)
        raise _twilio_http_error(request, {"code": 20003, "message": "Authenticate", "status": 401})

    monkeypatch.setattr("app.services.alerts.urllib.request.urlopen", fake_urlopen)
    provider = TwilioProvider("AC123", "secret-token", "+17370000000", content_sid="HXtemplate")
    try:
        provider.send("+50255555555", "Tipo: Prueba de alerta", None)
    except AlertDeliveryError as exc:
        assert exc.twilio_code == 20003
        assert exc.reason == "Twilio 20003: Authenticate. Parámetros: From, To, Body"
    else:
        raise AssertionError("expected Twilio failure")
    assert len(calls) == 1


def test_empty_twilio_settings_stay_on_the_console(monkeypatch) -> None:
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(settings, "twilio_whatsapp_from", "")
    assert get_provider().name == "console"
    monkeypatch.setattr(settings, "twilio_account_sid", "AC123")
    assert get_provider().name == "console"
    monkeypatch.setattr(settings, "twilio_auth_token", "token")
    monkeypatch.setattr(settings, "twilio_whatsapp_from", "whatsapp:+14155238886")
    assert get_provider().name == "twilio"


def test_sensor_crud_is_tenant_scoped_and_operators_cannot_write(client, accounts) -> None:
    owner = accounts()
    outsider = accounts()
    headers, _camera_id, _zone_id, token = open_site(client, owner)
    site_id = client.get("/sites", headers=headers).json()[0]["id"]
    created = _sensor(client, headers, site_id)
    assert created["external_id"] == "puerta-bodega"
    assert client.post(
        "/sensors",
        json={"site_id": site_id, "name": "Otra", "sensor_type": "door", "external_id": "puerta-bodega"},
        headers=headers,
    ).status_code == 409
    assert client.get("/sensors", headers=auth_header(client, outsider)).json() == []
    operator = client.post(
        "/users",
        json={"email": f"op-{uuid.uuid4()}@example.com", "password": "password1", "full_name": "Operador", "role": "operator"},
        headers=headers,
    )
    operator_headers = auth_header(client, {"email": operator.json()["email"], "password": "password1"})
    assert len(client.get("/sensors", headers=operator_headers).json()) == 1
    assert client.post(
        "/sensors",
        json={"site_id": site_id, "name": "Otra", "sensor_type": "motion", "external_id": "mov-1"},
        headers=operator_headers,
    ).status_code == 403
    config = client.get("/device/config", headers=device_headers(token))
    assert config.json()["sensors"][0]["external_id"] == "puerta-bodega"


def test_motion_is_stored_without_an_alert_and_a_repeat_is_cooled(client, accounts, monkeypatch) -> None:
    recorder = RecordingProvider()
    _use(monkeypatch, recorder)
    headers, _camera_id, _zone_id, token = open_site(client, accounts())
    site_id = client.get("/sites", headers=headers).json()[0]["id"]
    _contact(client, headers)
    sensor = _sensor(client, headers, site_id, "motion", "pasillo", "Pasillo")
    now = datetime.now(timezone.utc)
    created = _sensor_event(client, token, sensor["id"], "motion", now)
    assert created.status_code == 200
    assert created.json()["created"] is True
    listed = client.get("/events", headers=headers).json()
    assert listed[0]["event_type"] == "motion"
    assert listed[0]["severity"] == "low"
    assert listed[0]["sensor_name"] == "Pasillo"
    assert client.get("/alerts/logs", headers=headers).json() == []
    assert recorder.sent == []
    repeat = _sensor_event(client, token, sensor["id"], "motion", now + timedelta(seconds=30))
    assert repeat.json()["created"] is False
    mismatch = _sensor_event(client, token, sensor["id"], "smoke", now)
    assert mismatch.status_code == 422


def test_alert_cooldown_suppresses_repeats_and_critical_always_sends(client, accounts, monkeypatch) -> None:
    recorder = RecordingProvider()
    _use(monkeypatch, recorder)
    headers, camera_id, zone_id, token = open_site(client, accounts())
    site_id = client.get("/sites", headers=headers).json()[0]["id"]
    _contact(client, headers)
    _contact(client, headers, phone="+50255555556", enabled=False, name="Inactivo")
    now = datetime.now(timezone.utc)
    first = _camera_event(client, token, camera_id, zone_id, now - timedelta(minutes=5))
    assert first.json()["created"] is True
    second = _camera_event(client, token, camera_id, zone_id, now)
    assert second.json()["created"] is True
    other = client.post(f"/cameras/{camera_id}/zones", json=_zone("Bodega"), headers=headers)
    assert other.status_code == 201
    third = _camera_event(client, token, camera_id, other.json()["id"], now)
    assert third.json()["created"] is True
    assert len(recorder.sent) == 2
    assert "Cámara: Acceso" in recorder.sent[0][1]
    assert "Sitio: Planta" in recorder.sent[0][1]
    assert "Severidad: Alta" in recorder.sent[0][1]
    assert recorder.sent[0][2] is None
    logs = client.get("/alerts/logs", headers=headers).json()
    suppressed = [row for row in logs if row["status"] == "suppressed"]
    assert len(suppressed) == 1
    assert suppressed[0]["detail"] == "Enfriamiento de alertas"
    assert suppressed[0]["contact_name"] is None
    assert suppressed[0]["is_test"] is False
    door = _sensor(client, headers, site_id)
    smoke = _sensor(client, headers, site_id, "smoke", "humo-1", "Detector")
    panic = _sensor(client, headers, site_id, "panic", "panico-1", "Botón")
    before = len(recorder.sent)
    assert _sensor_event(client, token, smoke["id"], "smoke", now - timedelta(minutes=5)).json()["created"] is True
    assert _sensor_event(client, token, smoke["id"], "smoke", now).json()["created"] is True
    panic_event = _sensor_event(client, token, panic["id"], "panic", now)
    assert panic_event.json()["created"] is True
    assert len(recorder.sent) == before + 3
    assert "Sensor: Detector" in recorder.sent[before][1]
    assert "Severidad: Crítico" in recorder.sent[before][1]
    door_event = _sensor_event(client, token, door["id"], "door_open", now)
    assert door_event.json()["created"] is True
    rows = client.get("/events", headers=headers).json()
    severities = {row["event_type"]: row["severity"] for row in rows}
    assert severities["smoke"] == "critical"
    assert severities["panic"] == "critical"
    assert severities["door_open"] == "medium"


def test_snapshot_is_attached_only_when_a_public_base_url_is_set(client, accounts, monkeypatch) -> None:
    recorder = RecordingProvider()
    _use(monkeypatch, recorder)
    monkeypatch.setattr(settings, "public_base_url", "")
    headers, camera_id, zone_id, token = open_site(client, accounts())
    _contact(client, headers)
    now = datetime.now(timezone.utc)
    plain = _camera_event(client, token, camera_id, zone_id, now - timedelta(minutes=5), snapshot=True)
    assert plain.json()["created"] is True
    assert recorder.sent[-1][2] is None
    monkeypatch.setattr(settings, "public_base_url", "https://alerts.example")
    other = client.post(f"/cameras/{camera_id}/zones", json=_zone("Patio"), headers=headers)
    pictured = _camera_event(client, token, camera_id, other.json()["id"], now, snapshot=True)
    assert pictured.json()["created"] is True
    media = recorder.sent[-1][2]
    assert media is not None
    assert media.startswith("https://alerts.example/public/snapshots/")
    token_part = media.rsplit("/", 1)[1]
    snapshot = client.get(f"/public/snapshots/{token_part}")
    assert snapshot.status_code == 200
    assert snapshot.content.startswith(b"\xff\xd8")
    broken = token_part[:-1] + ("a" if token_part[-1] != "a" else "b")
    assert client.get(f"/public/snapshots/{broken}").status_code == 404
    expired = snapshot_token(uuid.UUID(pictured.json()["id"]), int(datetime.now(timezone.utc).timestamp()) - 10)
    assert client.get(f"/public/snapshots/{expired}").status_code == 404


def test_twilio_failure_is_stored_with_the_reason(client, accounts, monkeypatch) -> None:
    _use(monkeypatch, FailingProvider())
    headers, camera_id, zone_id, token = open_site(client, accounts())
    _contact(client, headers)
    created = _camera_event(client, token, camera_id, zone_id, datetime.now(timezone.utc) - timedelta(minutes=5))
    assert created.json()["created"] is True
    logs = client.get("/alerts/logs", headers=headers).json()
    assert logs[0]["status"] == "failed"
    assert logs[0]["detail"] == "Twilio: sandbox"
    assert logs[0]["provider"] == "twilio"


def test_missing_contacts_are_a_failed_attempt(client, accounts, monkeypatch) -> None:
    _use(monkeypatch, RecordingProvider())
    headers, camera_id, zone_id, token = open_site(client, accounts())
    created = _camera_event(client, token, camera_id, zone_id, datetime.now(timezone.utc))
    assert created.json()["created"] is True
    logs = client.get("/alerts/logs", headers=headers).json()
    assert len(logs) == 1
    assert logs[0]["status"] == "failed"
    assert logs[0]["detail"] == "No hay contactos activos"
    assert logs[0]["is_test"] is False


def test_the_test_button_does_not_create_an_event(client, accounts, monkeypatch) -> None:
    recorder = RecordingProvider()
    _use(monkeypatch, recorder)
    account = accounts()
    headers = auth_header(client, account)
    metrics_before = client.get("/metrics", headers=headers).json()["events_per_day"]
    assert client.post("/alerts/test", headers=headers).json()["message"] == "No hay contactos activos"
    _contact(client, headers)
    first = client.post("/alerts/test", headers=headers)
    second = client.post("/alerts/test", headers=headers)
    assert first.json()["message"] == "Alerta de prueba enviada"
    assert second.json()["message"] == "Alerta de prueba enviada"
    assert client.get("/events", headers=headers).json() == []
    assert client.get("/metrics", headers=headers).json()["events_per_day"] == metrics_before
    logs = client.get("/alerts/logs", headers=headers).json()
    tests = [row for row in logs if row["is_test"]]
    assert len(tests) == 3
    assert all(row["event_id"] is None for row in tests)
    assert len(recorder.sent) == 2
    assert "Tipo: Prueba de alerta" in recorder.sent[0][1]
    assert "Origen: Prueba" in recorder.sent[0][1]
    assert recorder.sent[0][2] is None
    operator = client.post(
        "/users",
        json={"email": f"op-{uuid.uuid4()}@example.com", "password": "password1", "full_name": "Operador", "role": "operator"},
        headers=headers,
    )
    operator_headers = auth_header(client, {"email": operator.json()["email"], "password": "password1"})
    assert client.post("/alerts/test", headers=operator_headers).status_code == 403
    assert client.get("/alerts/contacts", headers=operator_headers).status_code == 403


def _zone(name: str) -> dict:
    from tests.test_device import zone_body

    body = zone_body()
    body["name"] = name
    return body


class _JsonResponse:
    status = 200

    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _telegram_token(monkeypatch, token: str = "123456:ABC-test") -> str:
    monkeypatch.setattr(settings, "telegram_bot_token", token)
    return token


def _capture_telegram(monkeypatch, payload: dict | None = None):
    calls: list[urllib.request.Request] = []

    def fake_urlopen(request, timeout=15):
        assert timeout == 15
        calls.append(request)
        return _JsonResponse({"ok": True, "result": {"message_id": 1}} if payload is None else payload)

    monkeypatch.setattr("app.services.alerts.urllib.request.urlopen", fake_urlopen)
    return calls


def _telegram_contact(client, headers, chat_id="424242", enabled=True, name="Ana"):
    response = client.post(
        "/alerts/contacts",
        json={"name": name, "channel": "telegram", "chat_id": chat_id, "enabled": enabled},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["channel"] == "telegram"
    assert body["chat_id"] == chat_id
    assert body["phone"] is None
    return body


def _parts(request: urllib.request.Request) -> dict[str, tuple[str | None, bytes]]:
    header = request.get_header("Content-type")
    assert header is not None
    assert header.startswith("multipart/form-data; boundary=")
    boundary = header.split("boundary=", 1)[1].encode()
    assert request.data is not None
    found: dict[str, tuple[str | None, bytes]] = {}
    for chunk in request.data.split(b"--" + boundary):
        if not chunk or chunk in (b"--", b"--\r\n"):
            continue
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        head, separator, content = chunk.partition(b"\r\n\r\n")
        if not separator:
            continue
        disposition = head.decode()
        name = disposition.split('name="', 1)[1].split('"', 1)[0]
        filename = None
        if 'filename="' in disposition:
            filename = disposition.split('filename="', 1)[1].split('"', 1)[0]
        found[name] = (filename, content)
    return found


def test_telegram_send_photo_is_a_direct_upload(monkeypatch) -> None:
    token = "123456:ABC-test"
    calls = _capture_telegram(monkeypatch)
    TelegramProvider(token).send("424242", "Tipo: Intrusión\nSeveridad: Alta", JPEG)
    assert len(calls) == 1
    request = calls[0]
    assert request.full_url == f"https://api.telegram.org/bot{token}/sendPhoto"
    assert request.data is not None
    assert not request.data.startswith(b"{")
    parts = _parts(request)
    assert list(parts) == ["chat_id", "caption", "photo"]
    assert parts["chat_id"] == (None, b"424242")
    assert parts["caption"][1].decode() == "Tipo: Intrusión\nSeveridad: Alta"
    assert parts["photo"][0] == "event.jpg"
    assert parts["photo"][1] == JPEG
    assert b"MediaUrl" not in request.data
    assert token.encode() not in request.data


def test_telegram_text_uses_send_message(monkeypatch) -> None:
    token = "123456:ABC-test"
    calls = _capture_telegram(monkeypatch)
    TelegramProvider(token).send("424242", "Tipo: Prueba de alerta\nOrigen: Prueba", None)
    assert len(calls) == 1
    request = calls[0]
    assert request.full_url == f"https://api.telegram.org/bot{token}/sendMessage"
    assert request.get_header("Content-type") == "application/json"
    assert request.data is not None
    body = json.loads(request.data)
    assert body == {"chat_id": "424242", "text": "Tipo: Prueba de alerta\nOrigen: Prueba"}


def test_telegram_error_hides_the_token(monkeypatch) -> None:
    token = "999888:SECRET-token"

    def fake_urlopen(request, timeout=15):
        assert timeout == 15
        raise urllib.error.HTTPError(
            request.full_url,
            400,
            "Bad Request",
            HTTPMessage(),
            io.BytesIO(json.dumps({"ok": False, "error_code": 400, "description": f"Bad Request: chat not found {token}"}).encode()),
        )

    monkeypatch.setattr("app.services.alerts.urllib.request.urlopen", fake_urlopen)
    try:
        TelegramProvider(token).send("424242", "Tipo: Prueba de alerta", None)
    except AlertDeliveryError as exc:
        reason = exc.reason
    else:
        raise AssertionError("expected Telegram failure")
    assert reason == "Telegram 400: Bad Request: chat not found [token]"
    assert token not in reason
    assert "SECRET" not in reason


def test_contact_channel_keeps_whatsapp_and_telegram_apart(client, accounts) -> None:
    owner = accounts()
    headers = auth_header(client, owner)
    created = _contact(client, headers)
    assert created["channel"] == "whatsapp"
    assert created["chat_id"] is None
    assert created["phone"] == "+50255555555"
    missing_chat = client.post("/alerts/contacts", json={"name": "Ana", "channel": "telegram"}, headers=headers)
    assert missing_chat.status_code == 422
    assert "Elige un chat de Telegram" in missing_chat.json()["detail"]
    typed = client.post(
        "/alerts/contacts",
        json={"name": "Ana", "channel": "telegram", "chat_id": "abc"},
        headers=headers,
    )
    assert typed.status_code == 422
    mixed = client.post(
        "/alerts/contacts",
        json={"name": "Ana", "channel": "telegram", "chat_id": "424242", "phone": "+50255555555"},
        headers=headers,
    )
    assert mixed.status_code == 422
    first = _telegram_contact(client, headers)
    duplicate = client.post(
        "/alerts/contacts",
        json={"name": "Otra", "channel": "telegram", "chat_id": "424242"},
        headers=headers,
    )
    assert duplicate.status_code == 409
    outsider = auth_header(client, accounts())
    assert client.post(
        "/alerts/contacts",
        json={"name": "Ana", "channel": "telegram", "chat_id": first["chat_id"]},
        headers=outsider,
    ).status_code == 201


def test_telegram_chats_are_recent_start_messages(client, accounts, monkeypatch) -> None:
    token = _telegram_token(monkeypatch)
    calls = _capture_telegram(
        monkeypatch,
        {
            "ok": True,
            "result": [
                {
                    "update_id": 1,
                    "message": {
                        "message_id": 1,
                        "date": 10,
                        "text": "/start",
                        "chat": {"id": 7, "type": "private", "first_name": "Ana", "last_name": "Pérez", "username": "ana"},
                    },
                },
                {
                    "update_id": 2,
                    "message": {
                        "message_id": 2,
                        "date": 20,
                        "text": "hola",
                        "chat": {"id": 8, "type": "private", "first_name": "Luis"},
                    },
                },
                {
                    "update_id": 3,
                    "message": {
                        "message_id": 3,
                        "date": 30,
                        "text": "/start@SentinelBot ahora",
                        "chat": {"id": 9, "type": "private", "first_name": "Bea"},
                    },
                },
                {
                    "update_id": 4,
                    "message": {
                        "message_id": 4,
                        "date": 40,
                        "text": "/start",
                        "chat": {"id": 7, "type": "private", "first_name": "Ana", "last_name": "Pérez", "username": "ana"},
                    },
                },
            ],
        },
    )
    headers = auth_header(client, accounts())
    listed = client.get("/alerts/telegram/chats", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()
    assert [row["chat_id"] for row in rows] == ["7", "9"]
    assert rows[0]["label"] == "Ana Pérez"
    assert rows[0]["username"] == "ana"
    assert rows[1]["username"] is None
    assert len(calls) == 1
    assert calls[0].full_url == f"https://api.telegram.org/bot{token}/getUpdates"
    sent = json.loads(calls[0].data)
    assert sent["timeout"] == 0
    assert "offset" not in sent
    operator = client.post(
        "/users",
        json={"email": f"op-{uuid.uuid4()}@example.com", "password": "password1", "full_name": "Operador", "role": "operator"},
        headers=headers,
    )
    operator_headers = auth_header(client, {"email": operator.json()["email"], "password": "password1"})
    assert client.get("/alerts/telegram/chats", headers=operator_headers).status_code == 403
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    missing = client.get("/alerts/telegram/chats", headers=headers)
    assert missing.status_code == 503
    assert missing.json()["detail"] == "Telegram no está configurado"
    assert token not in missing.text


def test_telegram_uploads_the_snapshot_without_a_public_url(client, accounts, monkeypatch) -> None:
    recorder = RecordingProvider()
    _use(monkeypatch, recorder)
    token = _telegram_token(monkeypatch)
    monkeypatch.setattr(settings, "public_base_url", "")
    calls = _capture_telegram(monkeypatch)
    headers, camera_id, zone_id, device_token = open_site(client, accounts())
    _contact(client, headers)
    _telegram_contact(client, headers)
    created = _camera_event(client, device_token, camera_id, zone_id, datetime.now(timezone.utc), snapshot=True)
    assert created.json()["created"] is True
    assert recorder.sent[-1][2] is None
    assert "Tipo: Intrusión" in recorder.sent[-1][1]
    assert len(calls) == 1
    assert calls[0].full_url == f"https://api.telegram.org/bot{token}/sendPhoto"
    parts = _parts(calls[0])
    assert "Tipo: Intrusión" in parts["caption"][1].decode()
    assert "Severidad: Alta" in parts["caption"][1].decode()
    assert "Cámara: Acceso" in parts["caption"][1].decode()
    assert parts["photo"][1] == JPEG
    assert b"https://" not in parts["caption"][1]
    logs = client.get("/alerts/logs", headers=headers).json()
    sent = [row for row in logs if row["status"] == "sent"]
    assert {row["provider"] for row in sent} == {"console", "telegram"}
    assert all(token not in (row["detail"] or "") for row in logs)


def test_telegram_uses_the_same_alert_cooldown(client, accounts, monkeypatch) -> None:
    _telegram_token(monkeypatch)
    calls = _capture_telegram(monkeypatch)
    headers, camera_id, zone_id, device_token = open_site(client, accounts())
    site_id = client.get("/sites", headers=headers).json()[0]["id"]
    _telegram_contact(client, headers)
    now = datetime.now(timezone.utc)
    assert _camera_event(client, device_token, camera_id, zone_id, now - timedelta(minutes=5)).json()["created"] is True
    assert _camera_event(client, device_token, camera_id, zone_id, now).json()["created"] is True
    panic = _sensor(client, headers, site_id, "panic", "panico-tg", "Botón")
    assert _sensor_event(client, device_token, panic["id"], "panic", now).json()["created"] is True
    assert len(calls) == 2
    assert all(call.full_url.endswith("/sendMessage") for call in calls)
    logs = client.get("/alerts/logs", headers=headers).json()
    suppressed = [row for row in logs if row["status"] == "suppressed"]
    assert len(suppressed) == 1
    assert suppressed[0]["provider"] == "telegram"
    assert suppressed[0]["detail"] == "Enfriamiento de alertas"
    sent = [row for row in logs if row["status"] == "sent"]
    assert len(sent) == 2
    assert all(row["provider"] == "telegram" for row in sent)


def test_the_test_button_sends_every_active_channel(client, accounts, monkeypatch) -> None:
    recorder = RecordingProvider()
    _use(monkeypatch, recorder)
    _telegram_token(monkeypatch)
    calls = _capture_telegram(monkeypatch)
    headers = auth_header(client, accounts())
    _contact(client, headers)
    _telegram_contact(client, headers)
    _telegram_contact(client, headers, chat_id="515151", enabled=False, name="Inactivo")
    result = client.post("/alerts/test", headers=headers)
    assert result.json()["message"] == "Alerta de prueba enviada"
    assert len(recorder.sent) == 1
    assert "Tipo: Prueba de alerta" in recorder.sent[0][1]
    assert "Origen: Prueba" in recorder.sent[0][1]
    assert recorder.sent[0][2] is None
    assert len(calls) == 1
    assert calls[0].full_url.endswith("/sendMessage")
    body = json.loads(calls[0].data)
    assert body["chat_id"] == "424242"
    assert "Tipo: Prueba de alerta" in body["text"]
    assert "Origen: Prueba" in body["text"]
    logs = client.get("/alerts/logs", headers=headers).json()
    assert {row["provider"] for row in logs if row["status"] == "sent"} == {"console", "telegram"}
    assert client.get("/events", headers=headers).json() == []
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    failed = client.post("/alerts/test", headers=headers)
    assert failed.json()["message"] == "Algunos envíos fallaron"
    latest = client.get("/alerts/logs", headers=headers).json()
    telegram_failures = [row for row in latest if row["provider"] == "telegram" and row["status"] == "failed"]
    assert telegram_failures[0]["detail"] == "Telegram no está configurado"
