"""On-site MJPEG publish path. Encoding runs only while a viewer is connected."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import numpy as np

from app.overlay import annotate_live, encode_jpeg
from app.rules import Detection

STALE_SECONDS = 3


def prepare_live_dir(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.glob("*.viewers"):
        path.unlink()


def read_viewers(directory: Path, camera_id: str) -> int:
    try:
        return max(0, int((directory / f"{camera_id}.viewers").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return 0


def write_viewers(directory: Path, camera_id: str, count: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{camera_id}.viewers"
    temporary = directory / f"{camera_id}.viewers.tmp"
    temporary.write_text(str(max(0, count)), encoding="utf-8")
    temporary.replace(target)


class Audience:
    """Viewer counts for this process, mirrored to disk for the camera processes."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def join(self, camera_id: str) -> None:
        with self._lock:
            count = self._counts.get(camera_id, 0) + 1
            self._counts[camera_id] = count
            write_viewers(self.directory, camera_id, count)

    def leave(self, camera_id: str) -> None:
        with self._lock:
            count = max(0, self._counts.get(camera_id, 0) - 1)
            self._counts[camera_id] = count
            write_viewers(self.directory, camera_id, count)


class OrganizationRef:
    def __init__(self) -> None:
        self._value = ""
        self._lock = threading.Lock()

    def set(self, value: str) -> None:
        with self._lock:
            self._value = value

    def get(self) -> str:
        with self._lock:
            return self._value


def publish_watched(
    directory: Path,
    camera_id: str,
    frame: np.ndarray,
    zones: list,
    exclusions: list,
    detections: list[Detection],
    fps: int,
    people: int,
) -> bool:
    if read_viewers(directory, camera_id) <= 0:
        return False
    jpeg = encode_jpeg(annotate_live(frame, zones, exclusions, detections))
    if not jpeg:
        return False
    write_live_jpeg(directory, camera_id, jpeg, fps, people)
    return True


def write_live_jpeg(directory: Path, camera_id: str, jpeg: bytes, fps: int, people: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    picture = directory / f"{camera_id}.jpg"
    temporary = directory / f"{camera_id}.jpg.tmp"
    temporary.write_bytes(jpeg)
    temporary.replace(picture)
    meta = {"fps": int(fps), "people": int(people), "updated_at": time.time()}
    meta_path = directory / f"{camera_id}.json"
    meta_tmp = directory / f"{camera_id}.json.tmp"
    meta_tmp.write_text(json.dumps(meta), encoding="utf-8")
    meta_tmp.replace(meta_path)


def read_status(directory: Path, camera_id: str, now: float | None = None) -> dict:
    moment = time.time() if now is None else now
    try:
        meta = json.loads((directory / f"{camera_id}.json").read_text(encoding="utf-8"))
        updated = float(meta["updated_at"])
        fps = int(meta["fps"])
        people = int(meta["people"])
    except (OSError, ValueError, KeyError, TypeError):
        return {"signal": False, "fps": 0, "people": 0}
    jpeg = directory / f"{camera_id}.jpg"
    fresh = jpeg.is_file() and moment - updated <= STALE_SECONDS
    if not fresh:
        return {"signal": False, "fps": 0, "people": 0}
    return {"signal": True, "fps": fps, "people": people}


def read_jpeg(directory: Path, camera_id: str) -> bytes | None:
    if not read_status(directory, camera_id)["signal"]:
        return None
    try:
        data = (directory / f"{camera_id}.jpg").read_bytes()
    except OSError:
        return None
    if len(data) < 4 or not data.startswith(b"\xff\xd8"):
        return None
    return data
