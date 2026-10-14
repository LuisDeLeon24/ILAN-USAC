"""HTTPS client for the cloud API. The worker has no database credentials."""

from __future__ import annotations

import json

import httpx

PERMANENT_STATUS = {400, 404, 409, 422}


class PermanentError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"permanent api status {status}")
        self.status = status


class RetryableError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"retryable api status {status}")
        self.status = status


class ApiClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def heartbeat(self, model_version: str) -> None:
        self._request("POST", "/device/heartbeat", json={"model_version": model_version}, timeout=10)

    def config(self) -> dict:
        return self._request("GET", "/device/config", timeout=10)

    def post_event(self, meta: dict, snapshot: bytes | None) -> dict:
        files = None
        if snapshot:
            files = {"snapshot": ("snapshot.jpg", snapshot, "image/jpeg")}
        return self._request("POST", "/device/events", data={"meta": json.dumps(meta)}, files=files, timeout=30)

    def post_usage(self, payload: dict) -> dict:
        return self._request("POST", "/device/usage", json=payload, timeout=10)

    def post_sensor(self, payload: dict) -> dict:
        return self._request("POST", "/device/sensor-events", json=payload, timeout=15)

    def post_frame(self, camera_id: str, frame: bytes) -> dict:
        return self._request(
            "POST",
            "/device/frames",
            data={"camera_id": camera_id},
            files={"frame": ("frame.jpg", frame, "image/jpeg")},
            timeout=30,
        )

    def _request(self, method: str, path: str, timeout: float, **kwargs) -> dict:
        try:
            response = httpx.request(method, f"{self.base_url}{path}", headers=self.headers, timeout=timeout, **kwargs)
        except httpx.HTTPError as exc:
            raise RetryableError(0) from exc
        if response.is_success:
            if not response.content:
                return {}
            return response.json()
        if response.status_code in PERMANENT_STATUS:
            raise PermanentError(response.status_code)
        raise RetryableError(response.status_code)
