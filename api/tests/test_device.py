import base64
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.security import hash_device_token
from app.db.session import SessionLocal
from app.models.entities import Device, Site, UsageRecord, UsageReport
from tests.conftest import auth_header

JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
)
def device_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def attach_device(organization_id: str, site_id: str) -> str:
    token = f"device-{uuid.uuid4().hex}"
    db = SessionLocal()
    try:
        db.add(
            Device(
                organization_id=uuid.UUID(organization_id),
                site_id=uuid.UUID(site_id),
                name="Edge",
                token_hash=hash_device_token(token),
            )
        )
        db.commit()
    finally:
        db.close()
    return token


def zone_body(rule_type: str = "intrusion") -> dict:
    return {
        "name": "Acceso",
        "polygon": [[0.05, 0.05], [0.95, 0.05], [0.95, 0.95], [0.05, 0.95]],
        "schedule": {
            "timezone": "America/Guatemala",
            "windows": [{"days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "start": "00:00", "end": "23:59"}],
        },
        "rule_type": rule_type,
        "rule_params": {"seconds": 30} if rule_type == "loitering" else {},
    }


def open_site(client, account) -> tuple[dict[str, str], str, str, str]:
    headers = auth_header(client, account)
    site = client.post("/sites", json={"name": "Planta"}, headers=headers)
    assert site.status_code == 201
    site_id = site.json()["id"]
    camera = client.post(
        "/cameras",
        json={
            "site_id": site_id,
            "name": "Acceso",
            "source_type": "file",
            "file_path": "/videos/demo1.mp4",
            "fps": 2,
        },
        headers=headers,
    )
    assert camera.status_code == 201
    assert camera.json()["loop"] is False
    camera_id = camera.json()["id"]
    zone = client.post(f"/cameras/{camera_id}/zones", json=zone_body(), headers=headers)
    assert zone.status_code == 201
    token = attach_device(account["organization_id"], site_id)
    return headers, camera_id, zone.json()["id"], token


def event_meta(camera_id: str, zone_id: str | None, event_type: str = "intrusion", event_id: str | None = None) -> dict:
    return {
        "client_event_id": event_id or str(uuid.uuid4()),
        "camera_id": camera_id,
        "zone_id": zone_id,
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }


def test_file_camera_does_not_loop_unless_asked_and_rtsp_never_does(client, accounts) -> None:
    headers = auth_header(client, accounts())
    site = client.post("/sites", json={"name": "Nave"}, headers=headers)
    site_id = site.json()["id"]
    once = client.post(
        "/cameras",
        json={"site_id": site_id, "name": "Archivo", "source_type": "file", "file_path": "/videos/demo1.mp4"},
        headers=headers,
    )
    assert once.status_code == 201
    assert once.json()["loop"] is False
    looping = client.post(
        "/cameras",
        json={
            "site_id": site_id,
            "name": "Bucle",
            "source_type": "file",
            "file_path": "/videos/demo1.mp4",
            "loop": True,
        },
        headers=headers,
    )
    assert looping.status_code == 201
    assert looping.json()["loop"] is True
    streamed = client.post(
        "/cameras",
        json={"site_id": site_id, "name": "RTSP", "source_type": "rtsp", "rtsp_url": "rtsp://user:secret@10.0.0.8/live"},
        headers=headers,
    )
    assert streamed.status_code == 201
    assert streamed.json()["loop"] is False
    assert "secret" not in str(streamed.json())


def test_device_config_returns_the_rtsp_url_the_user_api_hides(client, accounts) -> None:
    account = accounts()
    headers = auth_header(client, account)
    site = client.post("/sites", json={"name": "Porter"}, headers=headers)
    site_id = site.json()["id"]
    created = client.post(
        "/cameras",
        json={
            "site_id": site_id,
            "name": "Calle",
            "source_type": "rtsp",
            "rtsp_url": "rtsp://operator:s3cret@10.4.4.8:554/live",
            "fps": 2,
        },
        headers=headers,
    )
    assert created.status_code == 201
    token = attach_device(account["organization_id"], site_id)
    config = client.get("/device/config", headers=device_headers(token))
    assert config.status_code == 200
    assert config.json()["cameras"][0]["rtsp_url"] == "rtsp://operator:s3cret@10.4.4.8:554/live"
    listed = client.get("/cameras", headers=headers)
    assert "s3cret" not in listed.text


def test_device_token_is_required(client) -> None:
    assert client.get("/device/config").status_code == 401
    assert client.get("/device/config", headers={"Authorization": "Bearer not-a-device"}).status_code == 401


def test_event_snapshot_usage_and_tenant_scope(client, accounts) -> None:
    owner = accounts()
    outsider = accounts()
    headers, camera_id, zone_id, token = open_site(client, owner)
    meta = event_meta(camera_id, zone_id)
    created = client.post(
        "/device/events",
        data={"meta": json.dumps(meta)},
        files={"snapshot": ("snap.jpg", JPEG, "image/jpeg")},
        headers=device_headers(token),
    )
    assert created.status_code == 200
    body = created.json()
    assert body["created"] is True
    event_id = body["id"]
    duplicate = client.post(
        "/device/events",
        data={"meta": json.dumps(meta)},
        files={"snapshot": ("snap.jpg", JPEG, "image/jpeg")},
        headers=device_headers(token),
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False
    assert duplicate.json()["id"] == event_id
    cooled = client.post(
        "/device/events",
        data={"meta": json.dumps(event_meta(camera_id, zone_id))},
        files={"snapshot": ("snap.jpg", JPEG, "image/jpeg")},
        headers=device_headers(token),
    )
    assert cooled.json()["created"] is False
    assert cooled.json()["id"] == event_id
    foreign = client.post(
        "/device/events",
        data={"meta": json.dumps(event_meta(str(uuid.uuid4()), zone_id))},
        headers=device_headers(token),
    )
    assert foreign.status_code == 404
    listed = client.get("/events", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["event_type"] == "intrusion"
    assert listed.json()[0]["severity"] == "high"
    assert listed.json()[0]["camera_name"] == "Acceso"
    assert listed.json()[0]["has_snapshot"] is True
    snapshot = client.get(f"/events/{event_id}/snapshot", headers=headers)
    assert snapshot.status_code == 200
    assert snapshot.content.startswith(b"\xff\xd8")
    hidden = client.get("/events", headers=auth_header(client, outsider))
    assert hidden.json() == []
    assert client.get(f"/events/{event_id}/snapshot", headers=auth_header(client, outsider)).status_code == 404
    operator = client.post(
        "/users",
        json={"email": f"op-{uuid.uuid4()}@example.com", "password": "password1", "full_name": "Operador", "role": "operator"},
        headers=headers,
    )
    assert operator.status_code == 201
    operator_headers = auth_header(client, {"email": operator.json()["email"], "password": "password1"})
    assert len(client.get("/events", headers=operator_headers).json()) == 1
    loitering = client.post(
        f"/cameras/{camera_id}/zones",
        json=zone_body("loitering"),
        headers=headers,
    )
    loiter_event = client.post(
        "/device/events",
        data={
            "meta": json.dumps(event_meta(camera_id, loitering.json()["id"], "loitering"))
        },
        files={"snapshot": ("snap.jpg", JPEG, "image/jpeg")},
        headers=device_headers(token),
    )
    assert loiter_event.status_code == 200
    rows = client.get("/events", headers=headers).json()
    severities = {row["event_type"]: row["severity"] for row in rows}
    assert severities["loitering"] == "medium"
    first_usage = client.post(
        "/device/usage",
        json={"client_report_id": "report-1", "camera_id": camera_id, "usage_date": "2026-10-01", "analyzed_minutes": 1},
        headers=device_headers(token),
    )
    assert first_usage.status_code == 200
    assert first_usage.json()["created"] is True
    replay = client.post(
        "/device/usage",
        json={"client_report_id": "report-1", "camera_id": camera_id, "usage_date": "2026-10-01", "analyzed_minutes": 1},
        headers=device_headers(token),
    )
    assert replay.json()["created"] is False
    second = client.post(
        "/device/usage",
        json={"client_report_id": "report-2", "camera_id": camera_id, "usage_date": "2026-10-01", "analyzed_minutes": 0.5},
        headers=device_headers(token),
    )
    assert second.status_code == 200
    db = SessionLocal()
    try:
        record = db.scalar(select(UsageRecord).where(UsageRecord.camera_id == uuid.UUID(camera_id)))
        reports = db.scalar(select(func.count()).select_from(UsageReport).where(UsageReport.camera_id == uuid.UUID(camera_id)))
        assert Decimal(record.analyzed_minutes) == Decimal("1.50")
        assert reports == 2
    finally:
        db.close()
    user_token = auth_header(client, owner)
    assert client.get("/device/config", headers=user_token).status_code == 401


def test_bootstrap_device_attaches_once_to_the_earliest_site(client, accounts, monkeypatch) -> None:
    token = "bootstrap-device-token"
    monkeypatch.setattr(settings, "bootstrap_device_token", token)
    headers = auth_header(client, accounts())
    created = client.post("/sites", json={"name": "Primero"}, headers=headers)
    assert created.status_code == 201
    db = SessionLocal()
    try:
        first = db.scalar(select(Device).where(Device.token_hash == hash_device_token(token)))
        earliest = db.scalar(select(Site).order_by(Site.created_at.asc()))
        assert first is not None
        assert earliest is not None
        assert first.site_id == earliest.id
        assert first.name == "Dispositivo demo"
    finally:
        db.close()
    again = client.post("/sites", json={"name": "Segundo"}, headers=headers)
    assert again.status_code == 201
    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(Device).where(Device.token_hash == hash_device_token(token)))
        assert count == 1
        db.execute(delete(Device).where(Device.token_hash == hash_device_token(token)))
        db.commit()
    finally:
        db.close()
