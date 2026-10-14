"""Read a local video, sample frames, and post rule hits. The file never leaves the device."""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2

from app.buffer import Outbox
from app.client import ApiClient, PermanentError
from app.config import Settings, load_settings
from app.frames import claim_frame_upload, fit_width, select_detections
from app.meter import Meter
from app.live import publish_watched
from app.overlay import annotate, encode_jpeg, write_preview
from app.rules import VEHICLE_CLASSES, PERSON_CLASS, Cooldown, Detection, evaluate

logger = logging.getLogger("sentinel.worker")
REPORT_EVERY_MS = 15_000
CONFIG_REFRESH_S = 20


def load_model(path: Path):
    from ultralytics import YOLO

    path.parent.mkdir(parents=True, exist_ok=True)
    previous = Path.cwd()
    os.chdir(path.parent)
    try:
        if not path.exists():
            logger.info("downloading model %s", path.name)
        model = YOLO(path.name)
    finally:
        os.chdir(previous)
    logger.info("model ready path=%s", path)
    return model


def watch_camera(camera_id: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings()
    client = ApiClient(settings.api_base_url, settings.device_token)
    outbox = Outbox(settings.buffer_dir / camera_id)
    model = load_model(settings.model_path)
    cooldown = Cooldown()
    meter = Meter()
    played_once = False
    sent_frames: set[str] = set()
    while True:
        outbox.flush(client)
        try:
            config = client.config()
        except Exception:
            logger.exception("config request failed camera=%s", camera_id)
            time.sleep(5)
            continue
        camera = _find(config, camera_id)
        if camera is None:
            logger.info("camera removed camera=%s", camera_id)
            return
        if camera["source_type"] == "file" and not camera["loop"] and played_once:
            time.sleep(5)
            continue
        result = play(
            model=model,
            camera=camera,
            config=config,
            client=client,
            outbox=outbox,
            settings=settings,
            cooldown=cooldown,
            meter=meter,
            sent_frames=sent_frames,
        )
        if result == "removed":
            return
        if result == "ended":
            played_once = True
        else:
            time.sleep(5)


def play(
    *,
    model,
    camera: dict,
    config: dict,
    client: ApiClient,
    outbox: Outbox,
    settings: Settings,
    cooldown: Cooldown,
    meter: Meter,
    sent_frames: set[str],
) -> str:
    camera_id = camera["id"]
    source = camera["rtsp_url"] if camera["source_type"] == "rtsp" else camera["file_path"]
    if not source:
        _disconnect(camera_id, client, outbox, cooldown, config.get("cooldown_seconds", 60))
        return "failed"
    capture = cv2.VideoCapture()
    open_timeout = getattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC", None)
    read_timeout = getattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC", None)
    if open_timeout is not None:
        capture.set(open_timeout, 8000)
    if read_timeout is not None:
        capture.set(read_timeout, 8000)
    if not capture.open(source):
        logger.info("source closed camera=%s source_type=%s", camera_id, camera["source_type"])
        _disconnect(camera_id, client, outbox, cooldown, config.get("cooldown_seconds", 60))
        capture.release()
        return "failed"
    if getattr(model, "predictor", None) is not None:
        model.predictor = None
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 0
    target_fps = int(camera["fps"])
    if source_fps < 1:
        source_fps = float(target_fps)
    step = max(1, round(source_fps / target_fps))
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration_ms = (frame_count / source_fps) * 1000 if frame_count > 0 and camera["source_type"] == "file" else 0
    frame_index = 0
    last_ms = 0.0
    dwell: dict[tuple[str, int], float] = {}
    refresh_at = time.monotonic() + CONFIG_REFRESH_S
    timezone_name = config.get("timezone") or "America/Guatemala"
    cooldown_seconds = float(config.get("cooldown_seconds") or 60)
    try:
        while True:
            if time.monotonic() >= refresh_at:
                camera, timezone_name, cooldown_seconds, removed = _refresh(client, camera, timezone_name, cooldown_seconds)
                refresh_at = time.monotonic() + CONFIG_REFRESH_S
                if removed:
                    return "removed"
            ok, frame = capture.read()
            if not ok or frame is None:
                if camera["source_type"] == "rtsp":
                    _disconnect(camera_id, client, outbox, cooldown, cooldown_seconds)
                    return "failed"
                break
            if frame_index % step != 0:
                frame_index += 1
                continue
            reported_ms = capture.get(cv2.CAP_PROP_POS_MSEC) or 0
            if reported_ms > last_ms:
                position_ms = reported_ms
            elif camera["source_type"] == "rtsp":
                position_ms = last_ms + (1000 / target_fps)
            else:
                position_ms = last_ms
            meter.add_ms(last_ms, position_ms)
            last_ms = position_ms
            frame_index += 1
            frame = fit_width(frame)
            _maybe_frame(client, camera, frame, sent_frames)
            started = time.monotonic()
            confidence = float(camera.get("min_confidence") or 0.35)
            detections = select_detections(
                _track(model, frame, confidence),
                float(camera.get("min_box_area") or 0),
                camera.get("exclusions") or [],
            )
            persons = sum(1 for item in detections if item.class_id == PERSON_CLASS)
            vehicles = sum(1 for item in detections if item.class_id in VEHICLE_CLASSES)
            publish_watched(
                settings.live_dir,
                camera_id,
                frame,
                camera.get("zones") or [],
                camera.get("exclusions") or [],
                detections,
                target_fps,
                persons,
            )
            if persons or vehicles:
                logger.info("detection camera=%s persons=%s vehicles=%s", camera_id, persons, vehicles)
            hits = evaluate(
                camera_id=camera_id,
                zones=camera.get("zones") or [],
                detections=detections,
                moment=datetime.now(timezone.utc),
                video_time=position_ms / 1000,
                dwell=dwell,
                cooldown=cooldown,
                cooldown_seconds=cooldown_seconds,
                now=time.monotonic(),
            )
            annotated = annotate(frame, camera.get("zones") or [], detections)
            write_preview(annotated, settings.preview_dir, camera_id)
            if hits:
                jpeg = encode_jpeg(annotated)
                for hit in hits:
                    _submit_event(
                        client,
                        outbox,
                        {
                            "client_event_id": str(uuid.uuid4()),
                            "camera_id": camera_id,
                            "zone_id": hit.zone_id,
                            "event_type": hit.event_type,
                            "occurred_at": datetime.now(timezone.utc).isoformat(),
                        },
                        jpeg,
                    )
            report = meter.take(REPORT_EVERY_MS)
            if report:
                _submit_usage(client, outbox, camera_id, report, timezone_name)
            elapsed = time.monotonic() - started
            period = 1 / target_fps
            if elapsed < period:
                time.sleep(period - elapsed)
    finally:
        capture.release()
    if duration_ms > last_ms:
        meter.add_ms(last_ms, duration_ms)
    report = meter.flush()
    if report:
        _submit_usage(client, outbox, camera_id, report, timezone_name)
    logger.info("file ended camera=%s loop=%s", camera_id, camera.get("loop"))
    return "ended"


def _refresh(client: ApiClient, camera: dict, timezone_name: str, cooldown_seconds: float):
    try:
        config = client.config()
    except Exception:
        logger.exception("config refresh failed camera=%s", camera["id"])
        return camera, timezone_name, cooldown_seconds, False
    match = _find(config, camera["id"])
    if match is None:
        return camera, timezone_name, cooldown_seconds, True
    return match, config.get("timezone") or timezone_name, float(config.get("cooldown_seconds") or cooldown_seconds), False


def _find(config: dict, camera_id: str) -> dict | None:
    for camera in config.get("cameras") or []:
        if camera["id"] == camera_id:
            return camera
    return None


def _maybe_frame(client: ApiClient, camera: dict, frame, sent: set[str]) -> None:
    camera_id = camera["id"]
    if not claim_frame_upload(camera_id, bool(camera.get("frame_requested")), sent):
        return
    jpeg = encode_jpeg(frame)
    if not jpeg:
        return
    try:
        client.post_frame(camera_id, jpeg)
    except PermanentError:
        logger.exception("frame rejected camera=%s", camera_id)
        sent.add(camera_id)
        return
    except Exception:
        logger.info("frame upload will retry camera=%s", camera_id)
        return
    sent.add(camera_id)
    logger.info("frame sent camera=%s", camera_id)


def _track(model, frame, min_confidence: float) -> list[Detection]:
    try:
        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
            classes=[PERSON_CLASS, *sorted(VEHICLE_CLASSES)],
            conf=min_confidence,
        )
    except Exception:
        logger.exception("track failed")
        return []
    boxes = results[0].boxes if results else None
    if boxes is None or boxes.xyxy is None:
        return []
    height, width = frame.shape[:2]
    if width == 0 or height == 0:
        return []
    xyxy = boxes.xyxy.cpu().numpy()
    classes = boxes.cls.cpu().numpy()
    identities = boxes.id.cpu().numpy() if boxes.id is not None else None
    detections: list[Detection] = []
    for index, raw in enumerate(xyxy):
        x1, y1, x2, y2 = (float(raw[0]) / width, float(raw[1]) / height, float(raw[2]) / width, float(raw[3]) / height)
        track_id = int(identities[index]) if identities is not None else None
        detections.append(Detection(int(classes[index]), track_id, (x1, y1, x2, y2)))
    return detections


def _disconnect(camera_id: str, client: ApiClient, outbox: Outbox, cooldown: Cooldown, cooldown_seconds: float) -> None:
    if not cooldown.allow(f"{camera_id}:disconnected", time.monotonic(), cooldown_seconds):
        return
    _submit_event(
        client,
        outbox,
        {
            "client_event_id": str(uuid.uuid4()),
            "camera_id": camera_id,
            "zone_id": None,
            "event_type": "camera_disconnected",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
        None,
    )


def _submit_event(client: ApiClient, outbox: Outbox, meta: dict, snapshot: bytes | None) -> None:
    try:
        client.post_event(meta, snapshot)
    except PermanentError:
        logger.exception("event rejected camera=%s type=%s", meta["camera_id"], meta["event_type"])
        return
    except Exception:
        logger.info("event buffered camera=%s type=%s", meta["camera_id"], meta["event_type"])
        outbox.add_event(meta["client_event_id"], meta, snapshot)
        return
    logger.info("event sent camera=%s type=%s", meta["camera_id"], meta["event_type"])


def _submit_usage(client: ApiClient, outbox: Outbox, camera_id: str, minutes: float, timezone_name: str) -> None:
    payload = {
        "client_report_id": str(uuid.uuid4()),
        "camera_id": camera_id,
        "usage_date": datetime.now(ZoneInfo(timezone_name)).date().isoformat(),
        "analyzed_minutes": minutes,
    }
    try:
        client.post_usage(payload)
    except PermanentError:
        logger.exception("usage rejected camera=%s", camera_id)
        return
    except Exception:
        logger.info("usage buffered camera=%s minutes=%s", camera_id, minutes)
        outbox.add_usage(payload["client_report_id"], payload)
        return
    logger.info("usage sent camera=%s minutes=%s", camera_id, minutes)
