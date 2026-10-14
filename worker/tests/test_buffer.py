from app.buffer import Outbox
from app.client import PermanentError, RetryableError


class FakeApi:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.usage: list[dict] = []
        self.event_failures = 0

    def post_event(self, meta: dict, snapshot: bytes | None) -> dict:
        if self.event_failures:
            self.event_failures -= 1
            raise RetryableError(503)
        self.events.append({"meta": meta, "snapshot": snapshot})
        return {"created": True}

    def post_usage(self, payload: dict) -> dict:
        self.usage.append(payload)
        return {"created": True}


def test_outbox_keeps_an_event_until_the_api_accepts_it(tmp_path) -> None:
    outbox = Outbox(tmp_path)
    api = FakeApi()
    api.event_failures = 1
    outbox.add_event("evt-1", {"client_event_id": "evt-1", "event_type": "intrusion"}, b"jpeg-bytes")
    outbox.flush(api)
    assert api.events == []
    outbox.flush(api)
    assert api.events[0]["meta"]["event_type"] == "intrusion"
    assert api.events[0]["snapshot"] == b"jpeg-bytes"
    outbox.flush(api)
    assert len(api.events) == 1


def test_outbox_drops_a_permanently_rejected_event(tmp_path) -> None:
    outbox = Outbox(tmp_path)

    class Rejecting:
        def post_event(self, meta: dict, snapshot: bytes | None) -> dict:
            raise PermanentError(422)

        def post_usage(self, payload: dict) -> dict:
            return {}

    outbox.add_event("evt-2", {"client_event_id": "evt-2"}, None)
    outbox.flush(Rejecting())
    fresh = Outbox(tmp_path)
    api = FakeApi()
    fresh.flush(api)
    assert api.events == []
