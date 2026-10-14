import threading

import httpx
import pytest

from app.buffer import Outbox
from app.client import PermanentError, RetryableError
from app.rules import Cooldown
from app.sensors import SensorDirectory, decide, deliver, open_sensor_webhook

SENSORS = [
    {"id": "door-1", "external_id": "puerta-bodega", "sensor_type": "door"},
    {"id": "motion-1", "external_id": "pasillo", "sensor_type": "motion"},
    {"id": "smoke-1", "external_id": "humo", "sensor_type": "smoke"},
    {"id": "panic-1", "external_id": "panico", "sensor_type": "panic"},
]
WHEN = "2026-10-01T19:26:00+00:00"


@pytest.mark.parametrize(
    ("external_id", "state", "event_type"),
    [
        ("puerta-bodega", "open", "door_open"),
        ("pasillo", "detected", "motion"),
        ("humo", "alarm", "smoke"),
        ("panico", "pressed", "panic"),
    ],
)
def test_alarm_states_become_events(external_id, state, event_type) -> None:
    decision = decide(SENSORS, external_id, state, WHEN, Cooldown(), 60, 100)
    assert decision.status == 200
    assert decision.meta is not None
    assert decision.meta["event_type"] == event_type
    assert decision.meta["occurred_at"].startswith("2026-10-01T19:26:00")


@pytest.mark.parametrize(
    ("external_id", "state"),
    [("puerta-bodega", "closed"), ("pasillo", "clear"), ("humo", "clear"), ("panico", "clear")],
)
def test_quiet_states_do_not_create_events(external_id, state) -> None:
    decision = decide(SENSORS, external_id, state, WHEN, Cooldown(), 60, 100)
    assert decision.status == 200
    assert decision.meta is None
    assert decision.body["created"] is False


def test_unknown_sensor_and_bad_state_are_rejected() -> None:
    assert decide(SENSORS, "no-existe", "open", WHEN, Cooldown(), 60, 100).status == 404
    assert decide(SENSORS, "puerta-bodega", "ajar", WHEN, Cooldown(), 60, 100).status == 422


def test_sensor_cooldown_suppresses_a_repeat_until_the_window_passes() -> None:
    cooldown = Cooldown()
    first = decide(SENSORS, "puerta-bodega", "open", WHEN, cooldown, 60, 100)
    second = decide(SENSORS, "puerta-bodega", "open", WHEN, cooldown, 60, 130)
    third = decide(SENSORS, "puerta-bodega", "open", WHEN, cooldown, 60, 170)
    assert first.meta is not None
    assert second.meta is None
    assert third.meta is not None


def test_a_naive_timestamp_is_rejected_without_consuming_cooldown() -> None:
    cooldown = Cooldown()
    rejected = decide(SENSORS, "puerta-bodega", "open", "2026-10-01T19:26:00", cooldown, 60, 100)
    accepted = decide(SENSORS, "puerta-bodega", "open", WHEN, cooldown, 60, 100)
    assert rejected.status == 422
    assert accepted.meta is not None


class _Api:
    def __init__(self) -> None:
        self.payloads: list[dict] = []
        self.failures = 0

    def post_sensor(self, payload: dict) -> dict:
        if self.failures:
            self.failures -= 1
            raise RetryableError(503)
        self.payloads.append(payload)
        return {"created": True}


def test_webhook_rejects_a_bad_token_and_forwards_an_alarm(tmp_path) -> None:
    directory = SensorDirectory()
    directory.update({"sensors": SENSORS, "cooldown_seconds": 60})
    api = _Api()
    server = open_sensor_webhook("secret", directory, api, Outbox(tmp_path), Cooldown(), host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/sensors"
    body = {"external_id": "puerta-bodega", "state": "open", "occurred_at": WHEN}
    try:
        denied = httpx.post(url, json=body, timeout=5)
        assert denied.status_code == 401
        accepted = httpx.post(url, json=body, headers={"Authorization": "Bearer secret"}, timeout=5)
        assert accepted.status_code == 200
        assert accepted.json()["created"] is True
        assert api.payloads[0]["event_type"] == "door_open"
    finally:
        server.shutdown()
        server.server_close()


def test_a_failed_delivery_is_buffered_and_then_flushed(tmp_path) -> None:
    api = _Api()
    api.failures = 1
    outbox = Outbox(tmp_path)
    kind, created = deliver(api, outbox, {"client_event_id": "evt-1", "sensor_id": "door-1", "event_type": "door_open"})
    assert kind == "buffered"
    assert created is False
    outbox.flush(api)
    assert api.payloads[0]["event_type"] == "door_open"
    outbox.flush(api)
    assert len(api.payloads) == 1


def test_a_permanent_rejection_is_dropped(tmp_path) -> None:
    class Rejecting:
        def post_sensor(self, payload: dict) -> dict:
            raise PermanentError(422)

    outbox = Outbox(tmp_path)
    kind, _created = deliver(Rejecting(), outbox, {"client_event_id": "evt-2", "sensor_id": "door-1"})
    assert kind == "rejected"
    api = _Api()
    outbox.flush(api)
    assert api.payloads == []
