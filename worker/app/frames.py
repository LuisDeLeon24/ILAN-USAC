"""Resize sampled frames and drop detections the camera is configured to ignore."""

from __future__ import annotations

import cv2
import numpy as np

from app.rules import Detection, foot_point, point_in_polygon

MAX_FRAME_WIDTH = 1280


def fit_width(frame: np.ndarray, max_width: int = MAX_FRAME_WIDTH) -> np.ndarray:
    height, width = frame.shape[:2]
    if width <= max_width or width < 1 or height < 1:
        return frame
    scaled_height = max(1, int(round(height * (max_width / width))))
    return cv2.resize(frame, (max_width, scaled_height), interpolation=cv2.INTER_AREA)


def claim_frame_upload(camera_id: str, requested: bool, sent: set[str]) -> bool:
    """True only for the first upload while the device config still asks for a frame."""
    if not requested:
        sent.discard(camera_id)
        return False
    return camera_id not in sent


def select_detections(detections: list[Detection], min_box_area: float, exclusions: list) -> list[Detection]:
    polygons: list = []
    for item in exclusions:
        polygons.append(item["polygon"] if isinstance(item, dict) else item)
    kept: list[Detection] = []
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        if min_box_area > 0 and area < min_box_area:
            continue
        x_coord, y_coord = foot_point(detection.bbox)
        if any(point_in_polygon(x_coord, y_coord, polygon) for polygon in polygons):
            continue
        kept.append(detection)
    return kept
