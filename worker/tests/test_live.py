import threading
import time

import httpx
import numpy as np

from app.buffer import Outbox
from app.live import OrganizationRef, publish_watched, read_viewers, write_live_jpeg, write_viewers
from app.live_token import verify_live_token
from app.overlay import annotate, annotate_live
from app.rules import Cooldown
from app.sensors import SensorDirectory, open_sensor_webhook

SECRET = "test-live-secret-value"
ORG = "22222222-2222-2222-2222-222222222222"
CAMERA = "11111111-1111-1111-1111-111111111111"
# Issued by the API token helper with now=1700000000. The worker must accept this exact string.
GOLDEN = (
    "eyJjYW0iOiIxMTExMTExMS0xMTExLTExMTEtMTExMS0xMTExMTExMTExMTEiLCJleHAiOjE3MDAwMDAzMDAs"
    "Im9yZyI6IjIyMjIyMjIyLTIyMjItMjIyMi0yMjIyLTIyMjIyMjIyMjIyMiIsInB1cnBvc2UiOiJsaXZlIn0."
    "H873kf7m2ymN9HAUs2b0aeLml4SCnkx_4NpPci_PxBs"
)


def test_the_worker_accepts_the_api_token_and_rejects_an_expired_one() -> None:
    payload = verify_live_token(SECRET, GOLDEN, now=1_700_000_000)
    assert payload is not None
    assert payload["cam"] == CAMERA
    assert payload["org"] == ORG
    assert verify_live_token(SECRET, GOLDEN, now=1_700_000_300) is None
    assert verify_live_token(SECRET, GOLDEN[:-2] + "xx", now=1_700_000_000) is None


def test_encoding_waits_until_someone_is_watching(tmp_path) -> None:
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    exclusion = [{"polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}]
    assert publish_watched(tmp_path, CAMERA, frame, [], exclusion, [], 2, 4) is False
    assert not (tmp_path / f"{CAMERA}.jpg").exists()
    write_viewers(tmp_path, CAMERA, 1)
    assert publish_watched(tmp_path, CAMERA, frame, [], exclusion, [], 2, 4) is True
    assert (tmp_path / f"{CAMERA}.jpg").stat().st_size > 4


def test_live_overlay_draws_exclusion_areas_in_white() -> None:
    frame = np.zeros((80, 80, 3), dtype=np.uint8)
    exclusion = [{"polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}]
    plain = annotate(frame, [], [])
    marked = annotate_live(frame, [], exclusion, [])
    assert not np.array_equal(plain, marked)
    assert (marked == 255).all(axis=2).any()


def test_stream_rejects_a_bad_token_and_drops_the_viewer_when_the_client_leaves(tmp_path) -> None:
    live_dir = tmp_path / "live"
    organization = OrganizationRef()
    organization.set(ORG)
    server = open_sensor_webhook(
        "secret",
        SensorDirectory(),
        object(),
        Outbox(tmp_path / "out"),
        Cooldown(),
        host="127.0.0.1",
        port=0,
        live_dir=live_dir,
        live_secret=SECRET,
        organization=organization,
        cors_origin="http://localhost:3000",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}/live/{CAMERA}"
    write_live_jpeg(live_dir, CAMERA, b"\xff\xd8\xff\xd9", 2, 1)
    try:
        denied = httpx.get(f"{base}.mjpg?token=nope", timeout=5)
        assert denied.status_code == 401
        assert read_viewers(live_dir, CAMERA) == 0
        status = httpx.get(f"{base}/status?token={GOLDEN}", timeout=5)
        assert status.status_code == 401
        from app.live_token import issue_live_token

        token, _expires = issue_live_token(SECRET, ORG, CAMERA)
        status = httpx.get(f"{base}/status?token={token}", timeout=5)
        assert status.status_code == 200
        assert status.json()["signal"] is True
        assert status.json()["people"] == 1
        assert status.json()["fps"] == 2
        assert status.headers["access-control-allow-origin"] == "http://localhost:3000"
        with httpx.stream("GET", f"{base}.mjpg?token={token}", timeout=5) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
            body = b""
            for chunk in response.iter_bytes():
                body += chunk
                if b"\xff\xd8" in body:
                    break
        assert b"\xff\xd8" in body
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and read_viewers(live_dir, CAMERA) != 0:
            time.sleep(0.05)
        assert read_viewers(live_dir, CAMERA) == 0
    finally:
        server.shutdown()
        server.server_close()
