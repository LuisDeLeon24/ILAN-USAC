"""Verify short-lived live-stream tokens. Same format as the API issuer."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

PURPOSE = "live"
LIVE_TOKEN_SECONDS = 300


def issue_live_token(secret: str, organization_id: str, camera_id: str, now: int | None = None) -> tuple[str, int]:
    issued = int(time.time()) if now is None else now
    expires = issued + LIVE_TOKEN_SECONDS
    payload = {"cam": camera_id, "exp": expires, "org": organization_id, "purpose": PURPOSE}
    body = _body(payload)
    return f"{body}.{_sign(secret, body)}", expires


def _body(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def verify_live_token(secret: str, token: str, now: int | None = None) -> dict | None:
    if not secret or token.count(".") != 1:
        return None
    body, mac = token.split(".", 1)
    expected = _sign(secret, body)
    if len(expected) != len(mac) or not hmac.compare_digest(expected, mac):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("purpose") != PURPOSE:
        return None
    exp = payload.get("exp")
    moment = int(time.time()) if now is None else now
    if not isinstance(exp, int) or moment >= exp:
        return None
    if not payload.get("org") or not payload.get("cam"):
        return None
    return payload


def _sign(secret: str, body: str) -> str:
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")
