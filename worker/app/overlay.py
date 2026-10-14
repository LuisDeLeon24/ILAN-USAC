"""Draw zones and detections with the theme overlay color. Video stays on the device."""

from __future__ import annotations

import cv2
import numpy as np

from app.rules import VEHICLE_CLASSES, Detection
from app.theme_tokens import OVERLAY_BGR, OVERLAY_LINE_WIDTH

CLASS_LABELS = {0: "Persona", 2: "Vehiculo", 3: "Vehiculo", 5: "Vehiculo", 7: "Vehiculo"}
RULE_LABELS = {
    "intrusion": "Intrusion",
    "after_hours": "Fuera de horario",
    "loitering": "Merodeo",
    "occupancy": "Ocupacion",
}
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _stroke(width: int) -> int:
    return max(OVERLAY_LINE_WIDTH, round(width / 480))


def _font_scale(width: int) -> float:
    return max(0.8, width / 900)


def annotate_live(
    frame: np.ndarray,
    zones: list[dict],
    exclusions: list,
    detections: list[Detection],
) -> np.ndarray:
    canvas = annotate(frame, zones, detections)
    height, width = canvas.shape[:2]
    stroke = _stroke(width)
    for area in exclusions:
        polygon = area["polygon"] if isinstance(area, dict) else area
        points = np.array(
            [[int(float(point[0]) * width), int(float(point[1]) * height)] for point in polygon],
            dtype=np.int32,
        )
        if len(points) >= 3:
            _dashed_polygon(canvas, points, OVERLAY_BGR, stroke)
    return canvas


def _dashed_polygon(canvas: np.ndarray, points: np.ndarray, color: tuple[int, int, int], stroke: int) -> None:
    closed = np.vstack([points, points[0]])
    dash = stroke * 6
    gap = stroke * 4
    for start, end in zip(closed[:-1], closed[1:]):
        length = float(np.hypot(end[0] - start[0], end[1] - start[1]))
        if length < 1:
            continue
        direction = (end.astype(np.float64) - start.astype(np.float64)) / length
        cursor = 0.0
        draw = True
        while cursor < length:
            span = dash if draw else gap
            nxt = min(length, cursor + span)
            if draw:
                origin = start.astype(np.float64) + direction * cursor
                dest = start.astype(np.float64) + direction * nxt
                cv2.line(
                    canvas,
                    (int(origin[0]), int(origin[1])),
                    (int(dest[0]), int(dest[1])),
                    color,
                    stroke,
                    cv2.LINE_AA,
                )
            draw = not draw
            cursor = nxt


def annotate(frame: np.ndarray, zones: list[dict], detections: list[Detection]) -> np.ndarray:
    canvas = frame.copy()
    height, width = canvas.shape[:2]
    stroke = _stroke(width)
    font_scale = _font_scale(width)
    for zone in zones:
        points = np.array(
            [[int(float(point[0]) * width), int(float(point[1]) * height)] for point in zone["polygon"]],
            dtype=np.int32,
        )
        if len(points) >= 3:
            cv2.polylines(canvas, [points], True, OVERLAY_BGR, stroke)
            label = RULE_LABELS.get(zone["rule_type"], "")
            if label:
                origin = (int(points[0][0]), max(stroke * 8, int(points[0][1])))
                cv2.putText(canvas, label, origin, FONT, font_scale, OVERLAY_BGR, stroke, cv2.LINE_AA)
    for detection in detections:
        if detection.class_id != 0 and detection.class_id not in VEHICLE_CLASSES:
            continue
        x1, y1, x2, y2 = detection.bbox
        start = (int(x1 * width), int(y1 * height))
        end = (int(x2 * width), int(y2 * height))
        cv2.rectangle(canvas, start, end, OVERLAY_BGR, stroke)
        text = CLASS_LABELS.get(detection.class_id, "")
        if text:
            cv2.putText(
                canvas,
                text,
                (start[0], max(stroke * 8, start[1] - stroke * 2)),
                FONT,
                font_scale,
                OVERLAY_BGR,
                stroke,
                cv2.LINE_AA,
            )
    return canvas


def encode_jpeg(frame: np.ndarray) -> bytes | None:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        return None
    return encoded.tobytes()


def write_preview(frame: np.ndarray, directory, camera_id: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{camera_id}.jpg"
    temporary = directory / f"{camera_id}.tmp.jpg"
    if cv2.imwrite(str(temporary), frame):
        temporary.replace(target)
