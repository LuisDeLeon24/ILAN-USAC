import json
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.models.entities import Camera
from tests.test_device import JPEG, device_headers, event_meta, open_site, zone_body

GUATEMALA = ZoneInfo("America/Guatemala")


def local_noon(day_offset: int) -> datetime:
    today = datetime.now(GUATEMALA).date()
    return datetime.combine(today + timedelta(days=day_offset), time(12, 0), tzinfo=GUATEMALA)


def post_event(client, token: str, camera_id: str, zone_id: str, when: datetime, event_type: str = "intrusion"):
    meta = event_meta(camera_id, zone_id, event_type)
    meta["occurred_at"] = when.isoformat()
    return client.post(
        "/device/events",
        data={"meta": json.dumps(meta)},
        files={"snapshot": ("snap.jpg", JPEG, "image/jpeg")},
        headers=device_headers(token),
    )


def test_events_can_be_filtered_and_reviewed(client, accounts) -> None:
    headers, camera_id, zone_id, token = open_site(client, accounts())
    other = client.post(f"/cameras/{camera_id}/zones", json=zone_body("loitering"), headers=headers)
    assert other.status_code == 201
    other_zone = other.json()["id"]
    yesterday = post_event(client, token, camera_id, zone_id, local_noon(-1))
    assert yesterday.status_code == 200
    assert yesterday.json()["created"] is True
    today = post_event(client, token, camera_id, zone_id, datetime.now(GUATEMALA))
    assert today.status_code == 200
    assert today.json()["created"] is True
    medium = post_event(client, token, camera_id, other_zone, datetime.now(GUATEMALA), "loitering")
    assert medium.status_code == 200
    today_key = datetime.now(GUATEMALA).date().isoformat()
    same_day = client.get("/events", params={"start": today_key, "end": today_key}, headers=headers)
    assert same_day.status_code == 200
    assert yesterday.json()["id"] not in {row["id"] for row in same_day.json()}
    highs = client.get("/events", params={"start": today_key, "end": today_key, "severity": "high"}, headers=headers)
    assert {row["event_type"] for row in highs.json()} == {"intrusion"}
    loitering = client.get(
        "/events",
        params={"start": today_key, "end": today_key, "event_type": "loitering", "camera_id": camera_id},
        headers=headers,
    )
    assert len(loitering.json()) == 1
    assert loitering.json()[0]["status"] == "new"
    assert loitering.json()[0]["reviewed_at"] is None
    event_id = today.json()["id"]
    resolved = client.patch(f"/events/{event_id}", json={"status": "resolved"}, headers=headers)
    assert resolved.status_code == 200
    assert resolved.json()["reviewed_at"] is None
    review = client.patch(f"/events/{event_id}", json={"status": "in_review"}, headers=headers)
    assert review.status_code == 200
    assert review.json()["reviewed_at"]
    kept = client.patch(f"/events/{event_id}", json={"status": "resolved"}, headers=headers)
    assert kept.json()["reviewed_at"] == review.json()["reviewed_at"]
    marked = client.patch(f"/events/{medium.json()['id']}", json={"status": "false_positive"}, headers=headers)
    assert marked.json()["status"] == "false_positive"
    outsider = accounts()
    assert client.patch(f"/events/{event_id}", json={"status": "new"}, headers={"Authorization": f"Bearer {client.post('/auth/login', json={'email': outsider['email'], 'password': outsider['password']}).json()['access_token']}"}).status_code == 404


def test_operator_can_change_status_but_not_the_rate_or_a_frame(client, accounts) -> None:
    account = accounts()
    headers, camera_id, zone_id, token = open_site(client, account)
    created = post_event(client, token, camera_id, zone_id, datetime.now(GUATEMALA))
    operator = client.post(
        "/users",
        json={"email": f"op-{uuid.uuid4()}@example.com", "password": "password1", "full_name": "Operador", "role": "operator"},
        headers=headers,
    )
    assert operator.status_code == 201
    operator_headers = {
        "Authorization": f"Bearer {client.post('/auth/login', json={'email': operator.json()['email'], 'password': 'password1'}).json()['access_token']}"
    }
    changed = client.patch(f"/events/{created.json()['id']}", json={"status": "in_review"}, headers=operator_headers)
    assert changed.status_code == 200
    assert changed.json()["status"] == "in_review"
    assert client.put("/pricing", json={"rate_per_minute": 2}, headers=operator_headers).status_code == 403
    assert client.post(f"/cameras/{camera_id}/frame-request", headers=operator_headers).status_code == 403
    assert client.post(f"/cameras/{camera_id}/exclusions", json={"polygon": [[0, 0], [1, 0], [1, 1]]}, headers=operator_headers).status_code == 403


def test_metrics_use_the_month_and_the_configured_rate(client, accounts) -> None:
    headers, camera_id, _zone_id, token = open_site(client, accounts())
    created = post_event(client, token, camera_id, _zone_id, datetime.now(GUATEMALA))
    assert created.status_code == 200
    reviewed = client.patch(f"/events/{created.json()['id']}", json={"status": "in_review"}, headers=headers)
    assert reviewed.status_code == 200
    usage = client.post(
        "/device/usage",
        json={
            "client_report_id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "usage_date": datetime.now(GUATEMALA).date().isoformat(),
            "analyzed_minutes": 2.5,
        },
        headers=device_headers(token),
    )
    assert usage.status_code == 200
    priced = client.put("/pricing", json={"rate_per_minute": 1.5}, headers=headers)
    assert priced.status_code == 200
    assert priced.json()["currency"] == "GTQ"
    metrics = client.get("/metrics", headers=headers)
    assert metrics.status_code == 200
    body = metrics.json()
    assert body["analyzed_minutes"] == 2.5
    assert body["rate_per_minute"] == 1.5
    assert body["estimated_cost"] == 3.75
    assert body["average_response_seconds"] >= 0
    today = datetime.now(GUATEMALA).date().isoformat()
    today_count = next(day["count"] for day in body["events_per_day"] if day["date"] == today)
    assert today_count >= 1
    assert body["events_per_day"][0]["date"].endswith("-01")
    today_date = datetime.now(GUATEMALA).date()
    if today_date.day <= 3:
        assert body["previous_month_start"].endswith("-01")
        assert body["previous_month_start"] < body["month_start"]
        assert body["previous_analyzed_minutes"] == 0
        assert body["previous_estimated_cost"] == 0
    else:
        assert body["previous_month_start"] is None


def test_frame_request_uploads_one_clean_frame_that_expires(client, accounts) -> None:
    account = accounts()
    headers, camera_id, _zone_id, token = open_site(client, account)
    waiting = client.get(f"/cameras/{camera_id}/frame", headers=headers)
    assert waiting.status_code == 404
    requested = client.post(f"/cameras/{camera_id}/frame-request", headers=headers)
    assert requested.status_code == 200
    config = client.get("/device/config", headers=device_headers(token))
    camera = next(item for item in config.json()["cameras"] if item["id"] == camera_id)
    assert camera["frame_requested"] is True
    assert camera["min_confidence"] == 0.35
    assert camera["min_box_area"] == 0
    assert client.get(f"/cameras/{camera_id}/frame", headers=headers).status_code == 404
    stored = client.post(
        "/device/frames",
        data={"camera_id": camera_id},
        files={"frame": ("frame.jpg", JPEG, "image/jpeg")},
        headers=device_headers(token),
    )
    assert stored.status_code == 200
    assert stored.json()["received"] is True
    again = client.post(
        "/device/frames",
        data={"camera_id": camera_id},
        files={"frame": ("frame.jpg", JPEG, "image/jpeg")},
        headers=device_headers(token),
    )
    assert again.status_code == 409
    fresh = client.get("/device/config", headers=device_headers(token))
    updated = next(item for item in fresh.json()["cameras"] if item["id"] == camera_id)
    assert updated["frame_requested"] is False
    image = client.get(f"/cameras/{camera_id}/frame", headers=headers)
    assert image.status_code == 200
    assert image.content.startswith(b"\xff\xd8")
    outsider = accounts()
    outsider_headers = {
        "Authorization": f"Bearer {client.post('/auth/login', json={'email': outsider['email'], 'password': outsider['password']}).json()['access_token']}"
    }
    assert client.get(f"/cameras/{camera_id}/frame", headers=outsider_headers).status_code == 404
    db = SessionLocal()
    try:
        row = db.get(Camera, uuid.UUID(camera_id))
        row.preview_at = datetime.now(GUATEMALA) - timedelta(minutes=11)
        db.commit()
    finally:
        db.close()
    assert client.get(f"/cameras/{camera_id}/frame", headers=headers).status_code == 404


def test_detection_settings_and_exclusions_reach_the_device(client, accounts) -> None:
    headers, camera_id, _zone_id, token = open_site(client, accounts())
    invalid = client.patch(f"/cameras/{camera_id}", json={"min_confidence": 0.99}, headers=headers)
    assert invalid.status_code == 422
    updated = client.patch(f"/cameras/{camera_id}", json={"min_confidence": 0.8, "min_box_area": 0.02}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["min_confidence"] == 0.8
    assert updated.json()["min_box_area"] == 0.02
    polygon = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4]]
    created = client.post(f"/cameras/{camera_id}/exclusions", json={"polygon": polygon}, headers=headers)
    assert created.status_code == 201
    config = client.get("/device/config", headers=device_headers(token))
    camera = next(item for item in config.json()["cameras"] if item["id"] == camera_id)
    assert camera["min_confidence"] == 0.8
    assert camera["min_box_area"] == 0.02
    assert camera["exclusions"][0]["polygon"] == polygon
    assert client.patch(f"/exclusions/{created.json()['id']}", json={"polygon": [[0, 0], [1.2, 0], [1, 1]]}, headers=headers).status_code == 422
