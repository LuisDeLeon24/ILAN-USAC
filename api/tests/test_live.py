import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import User
from app.services.live_token import verify_live_token
from tests.conftest import auth_header
from tests.test_device import open_site

SECRET = "test-live-secret-value"
GOLDEN_ORG = uuid.UUID("22222222-2222-2222-2222-222222222222")
GOLDEN_CAMERA = uuid.UUID("11111111-1111-1111-1111-111111111111")
GOLDEN = (
    "eyJjYW0iOiIxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEiLCJleHAiOjE3MDAwMDAzMDAs"
    "Im9yZyI6IjIyMjIyMjIyLTIyMjItMjIyMi0yMjIyLTIyMjIyMjIyMjIyMiIsInB1cnBvc2UiOiJsaXZlIn0."
    "H873kf7m2ymN9HAUs2b0aeLml4SCnkx_4NpPci_PxBs"
)


def test_live_token_matches_the_worker_format() -> None:
    payload = verify_live_token(SECRET, GOLDEN, now=1_700_000_000)
    assert payload is not None
    assert payload["cam"] == str(GOLDEN_CAMERA)
    assert payload["org"] == str(GOLDEN_ORG)
    assert verify_live_token(SECRET, GOLDEN, now=1_700_000_300) is None


def test_a_user_receives_a_five_minute_token_for_their_camera(client, accounts, monkeypatch) -> None:
    monkeypatch.setattr(settings, "live_stream_secret", SECRET)
    monkeypatch.setattr(settings, "worker_public_url", "http://192.168.1.50:8081")
    account = accounts()
    headers, camera_id, _zone_id, _token = open_site(client, account)
    issued = client.post(f"/cameras/{camera_id}/live-token", headers=headers)
    assert issued.status_code == 200
    body = issued.json()
    assert body["stream_url"] == f"http://192.168.1.50:8081/live/{camera_id}.mjpg"
    assert body["status_url"] == f"http://192.168.1.50:8081/live/{camera_id}/status"
    assert "/backend" not in body["stream_url"]
    assert "token=" not in body["stream_url"]
    payload = verify_live_token(SECRET, body["token"])
    assert payload is not None
    assert payload["cam"] == camera_id
    assert payload["org"] == account["organization_id"]
    expires = datetime.fromisoformat(body["expires_at"])
    remaining = expires - datetime.now(timezone.utc)
    assert timedelta(minutes=4) < remaining <= timedelta(minutes=5)


def test_an_operator_can_watch_and_another_organization_cannot(client, accounts, monkeypatch) -> None:
    monkeypatch.setattr(settings, "live_stream_secret", SECRET)
    monkeypatch.setattr(settings, "worker_public_url", "http://localhost:8081")
    account = accounts()
    headers, camera_id, _zone_id, _token = open_site(client, account)
    db = SessionLocal()
    try:
        user = User(
            organization_id=uuid.UUID(account["organization_id"]),
            email=f"op-{uuid.uuid4().hex[:8]}@sentinel.local",
            full_name="Operador",
            password_hash=hash_password("operator-pass-1"),
            role="operator",
        )
        db.add(user)
        db.commit()
        email = user.email
    finally:
        db.close()
    operator = auth_header(client, {"email": email, "password": "operator-pass-1"})
    assert client.post(f"/cameras/{camera_id}/live-token", headers=operator).status_code == 200
    other = auth_header(client, accounts())
    assert client.post(f"/cameras/{camera_id}/live-token", headers=other).status_code == 404


def test_live_token_is_unavailable_until_the_worker_address_is_configured(client, accounts, monkeypatch) -> None:
    monkeypatch.setattr(settings, "live_stream_secret", "")
    monkeypatch.setattr(settings, "worker_public_url", "")
    account = accounts()
    headers, camera_id, _zone_id, _token = open_site(client, account)
    denied = client.post(f"/cameras/{camera_id}/live-token", headers=headers)
    assert denied.status_code == 503
    assert denied.json()["detail"] == "La vista en vivo no está configurada"
