"""Local sensor webhook. Readings stay on the edge device until the API accepts them."""

from __future__ import annotations

import hmac
import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.buffer import Outbox
from app.client import PermanentError
from app.live import Audience, OrganizationRef, prepare_live_dir, read_jpeg, read_status
from app.live_token import verify_live_token
from app.rules import Cooldown

logger = logging.getLogger("sentinel.worker")

ALARM_STATE = {
    "door": "open",
    "motion": "detected",
    "smoke": "alarm",
    "panic": "pressed",
}
QUIET_STATE = {
    "door": "closed",
    "motion": "clear",
    "smoke": "clear",
    "panic": "clear",
}
EVENT_TYPE = {
    "door": "door_open",
    "motion": "motion",
    "smoke": "smoke",
    "panic": "panic",
}
MAX_BODY = 65_536
LIVE_STREAM = re.compile(r"^/live/([0-9a-fA-F-]{36})\.mjpg$")
LIVE_STATUS = re.compile(r"^/live/([0-9a-fA-F-]{36})/status$")
STREAM_BOUNDARY = "sentinelliveboundary"


@dataclass
class Decision:
    status: int
    body: dict
    meta: dict | None = None


class SensorDirectory:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.sensors: list[dict] = []
        self.cooldown_seconds = 60.0

    def update(self, config: dict) -> None:
        with self._lock:
            self.sensors = list(config.get("sensors") or [])
            self.cooldown_seconds = float(config.get("cooldown_seconds") or 60)

    def snapshot(self) -> tuple[list[dict], float]:
        with self._lock:
            return list(self.sensors), self.cooldown_seconds


def decide(
    sensors: list[dict],
    external_id: str,
    state: str,
    occurred_at: str | None,
    cooldown: Cooldown,
    cooldown_seconds: float,
    now: float,
) -> Decision:
    match = next((sensor for sensor in sensors if sensor.get("external_id") == external_id), None)
    if match is None:
        return Decision(404, {"detail": "No encontrado"})
    sensor_type = str(match.get("sensor_type") or "")
    alarm = ALARM_STATE.get(sensor_type)
    quiet = QUIET_STATE.get(sensor_type)
    if state not in {alarm, quiet}:
        return Decision(422, {"detail": "Estado no válido"})
    if state != alarm:
        return Decision(200, {"accepted": True, "created": False})
    try:
        occurred = _occurred(occurred_at)
    except ValueError:
        return Decision(422, {"detail": "La fecha del evento debe incluir zona horaria"})
    event_type = EVENT_TYPE[sensor_type]
    key = f"sensor:{match['id']}:{event_type}"
    if not cooldown.allow(key, now, cooldown_seconds):
        return Decision(200, {"accepted": True, "created": False})
    return Decision(
        200,
        {"accepted": True, "created": True},
        {
            "client_event_id": str(uuid.uuid4()),
            "sensor_id": match["id"],
            "event_type": event_type,
            "occurred_at": occurred,
        },
    )


def deliver(client, outbox: Outbox, meta: dict) -> tuple[str, bool]:
    try:
        result = client.post_sensor(meta)
    except PermanentError:
        logger.exception("sensor event rejected sensor=%s", meta.get("sensor_id"))
        return "rejected", False
    except Exception:
        logger.info("sensor event buffered sensor=%s", meta.get("sensor_id"))
        outbox.add_sensor(meta["client_event_id"], meta)
        return "buffered", False
    logger.info("sensor event sent sensor=%s type=%s", meta.get("sensor_id"), meta.get("event_type"))
    return "sent", bool(result.get("created"))


def open_sensor_webhook(
    token: str,
    directory: SensorDirectory,
    client,
    outbox: Outbox,
    cooldown: Cooldown,
    host: str = "0.0.0.0",
    port: int = 8081,
    live_dir: Path | None = None,
    live_secret: str = "",
    organization: OrganizationRef | None = None,
    cors_origin: str = "",
) -> ThreadingHTTPServer:
    handler = _handler(token)
    server = ThreadingHTTPServer((host, port), handler)
    server.directory = directory  # type: ignore[attr-defined]
    server.client = client  # type: ignore[attr-defined]
    server.outbox = outbox  # type: ignore[attr-defined]
    server.cooldown = cooldown  # type: ignore[attr-defined]
    server.lock = threading.Lock()  # type: ignore[attr-defined]
    server.live_dir = live_dir  # type: ignore[attr-defined]
    server.live_secret = live_secret  # type: ignore[attr-defined]
    server.organization = organization or OrganizationRef()  # type: ignore[attr-defined]
    server.cors_origin = cors_origin  # type: ignore[attr-defined]
    server.audience = Audience(live_dir) if live_dir is not None else None  # type: ignore[attr-defined]
    if live_dir is not None:
        prepare_live_dir(live_dir)
    return server


def _handler(token: str):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_OPTIONS(self) -> None:  # noqa: N802
            path = urlsplit(self.path).path
            if LIVE_STREAM.match(path) or LIVE_STATUS.match(path):
                self.send_response(204)
                self._cors()
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._json(404, {"detail": "No encontrado"})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            stream = LIVE_STREAM.match(parsed.path)
            status = LIVE_STATUS.match(parsed.path)
            if stream is None and status is None:
                self._json(404, {"detail": "No encontrado"})
                return
            camera_id = (stream or status).group(1)
            token = parse_qs(parsed.query).get("token", [""])[0]
            payload = self._live_payload(camera_id, token)
            if payload is None:
                return
            if status is not None:
                self._live_json(200, read_status(self.server.live_dir, camera_id))
                return
            self.server.audience.join(camera_id)
            try:
                self._stream(camera_id, token)
            finally:
                self.server.audience.leave(camera_id)

        def do_POST(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] != "/sensors":
                self._json(404, {"detail": "No encontrado"})
                return
            if not _authorized(self.headers.get("Authorization"), token):
                self._json(401, {"detail": "No autorizado"})
                return
            length = int(self.headers.get("Content-Length") or "0")
            if length < 0 or length > MAX_BODY:
                self._json(422, {"detail": "Datos inválidos"})
                return
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                self._json(422, {"detail": "Datos inválidos"})
                return
            if not isinstance(payload, dict):
                self._json(422, {"detail": "Datos inválidos"})
                return
            external_id = str(payload.get("external_id") or "").strip()
            state = str(payload.get("state") or "").strip()
            if not external_id or not state:
                self._json(422, {"detail": "Datos inválidos"})
                return
            occurred = payload.get("occurred_at")
            occurred_at = None if occurred is None else str(occurred)
            sensors, seconds = self.server.directory.snapshot()
            with self.server.lock:
                decision = decide(
                    sensors,
                    external_id,
                    state,
                    occurred_at,
                    self.server.cooldown,
                    seconds,
                    time.monotonic(),
                )
                if decision.meta is not None:
                    kind, created = deliver(self.server.client, self.server.outbox, decision.meta)
                    decision.body["created"] = created if kind == "sent" else False
                    if kind == "buffered":
                        decision.body["buffered"] = True
            self._json(decision.status, decision.body)

        def log_message(self, fmt: str, *args) -> None:
            logger.info("edge http %s", urlsplit(self.path).path)

        def _live_payload(self, camera_id: str, token: str) -> dict | None:
            if self.server.live_dir is None or not self.server.live_secret:
                self._live_json(503, {"detail": "La vista en vivo no está configurada"})
                return None
            payload = verify_live_token(self.server.live_secret, token)
            organization = self.server.organization.get()
            if payload is None or payload["cam"] != camera_id or not organization or payload["org"] != organization:
                self._live_json(401, {"detail": "No autorizado"})
                return None
            return payload

        def _stream(self, camera_id: str, token: str) -> None:
            self.protocol_version = "HTTP/1.0"
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={STREAM_BOUNDARY}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Pragma", "no-cache")
            self._cors()
            self.end_headers()
            try:
                while verify_live_token(self.server.live_secret, token) is not None:
                    jpeg = read_jpeg(self.server.live_dir, camera_id)
                    if jpeg:
                        header = (
                            f"--{STREAM_BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                            f"Content-Length: {len(jpeg)}\r\n\r\n"
                        ).encode()
                        self.wfile.write(header)
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                        fps = read_status(self.server.live_dir, camera_id)["fps"]
                        time.sleep(1 / fps if fps in {2, 3, 4, 5} else 0.5)
                    else:
                        time.sleep(0.2)
            except OSError:
                return

        def _cors(self) -> None:
            origin = self.server.cors_origin
            if origin:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def _live_json(self, status: int, body: dict) -> None:
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(encoded)

        def _json(self, status: int, body: dict) -> None:
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return Handler


def _authorized(header: str | None, token: str) -> bool:
    if not header or not header.lower().startswith("bearer "):
        return False
    presented = header.split(" ", 1)[1].strip()
    if len(presented) != len(token):
        return False
    return hmac.compare_digest(presented, token)


def _occurred(value: str | None) -> str:
    if value is None or not value.strip():
        return datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone")
    return parsed.isoformat()
