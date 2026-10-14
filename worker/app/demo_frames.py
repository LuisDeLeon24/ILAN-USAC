"""Extract distinct frames from the demo video and store annotated JPEGs for the seed."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from app.rules import PERSON_CLASS, VEHICLE_CLASSES, Detection

logger = logging.getLogger("sentinel.worker")
MIN_FRAMES = 6
MAX_FRAMES = 8
CANDIDATES = 24


def choose_indexes(frame_count: int, samples: int) -> list[int]:
    if frame_count <= 0 or samples <= 0:
        return []
    count = min(samples, frame_count)
    if count == 1:
        return [frame_count // 2]
    chosen: list[int] = []
    seen: set[int] = set()
    for step in range(count):
        index = round(step * (frame_count - 1) / (count - 1))
        if index not in seen:
            seen.add(index)
            chosen.append(index)
    return chosen


def pick_positions(hits: list[bool], *, minimum: int = MIN_FRAMES, maximum: int = MAX_FRAMES) -> list[int]:
    detected = [index for index, hit in enumerate(hits) if hit]
    chosen = detected[:maximum]
    if len(chosen) >= minimum:
        return chosen
    for index in range(len(hits)):
        if index in chosen:
            continue
        chosen.append(index)
        if len(chosen) >= minimum:
            break
    return chosen[:maximum]


def _read_candidates(capture, indexes: list[int]) -> list:
    import cv2

    frames = []
    for index in indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = capture.read()
        if ok and frame is not None:
            frames.append(frame)
    if len(frames) >= MIN_FRAMES:
        return frames
    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
    sequential: list = []
    step = 0
    while len(sequential) < CANDIDATES:
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        if step % 15 == 0:
            sequential.append(frame)
        step += 1
    return sequential or frames


def _detections(frame, result) -> list[Detection]:
    boxes = result.boxes if result is not None else None
    if boxes is None or boxes.xyxy is None:
        return []
    height, width = frame.shape[:2]
    if width == 0 or height == 0:
        return []
    xyxy = boxes.xyxy.cpu().numpy()
    classes = boxes.cls.cpu().numpy()
    detections: list[Detection] = []
    for index, raw in enumerate(xyxy):
        bbox = (float(raw[0]) / width, float(raw[1]) / height, float(raw[2]) / width, float(raw[3]) / height)
        detections.append(Detection(int(classes[index]), None, bbox))
    return detections


def extract(video: Path, model, directory: Path) -> int:
    import cv2

    from app.frames import fit_width
    from app.overlay import annotate, encode_jpeg

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        print(f"No se pudo abrir {video}")
        capture.release()
        return 0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    indexes = choose_indexes(frame_count, CANDIDATES)
    saved: list[tuple[bool, bytes]] = []
    try:
        frames = _read_candidates(capture, indexes)
        if not frames:
            print(f"El video no tiene cuadros: {video}")
            return 0
        for index, frame in enumerate(frames):
            frame = fit_width(frame)
            try:
                results = model.predict(
                    frame,
                    verbose=False,
                    classes=[PERSON_CLASS, *sorted(VEHICLE_CLASSES)],
                    conf=0.35,
                )
            except Exception:
                logger.exception("demo frame detection failed index=%s", index)
                results = []
            detections = _detections(frame, results[0] if results else None)
            interesting = any(item.class_id == PERSON_CLASS or item.class_id in VEHICLE_CLASSES for item in detections)
            jpeg = encode_jpeg(annotate(frame, [], detections))
            if jpeg:
                saved.append((interesting, jpeg))
                logger.info("demo frame index=%s detections=%s", index, len(detections))
    finally:
        capture.release()
    chosen = pick_positions([hit for hit, _payload in saved])
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.glob("frame-*.jpg"):
        path.unlink()
    for order, position in enumerate(chosen, start=1):
        (directory / f"frame-{order:02d}.jpg").write_bytes(saved[position][1])
    return len(chosen)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    video = Path(os.environ.get("DEMO_VIDEO", "/videos/demo1.mp4"))
    directory = Path(os.environ.get("SEED_DIR", "/seed"))
    if not video.is_file():
        print(f"No está el video {video}")
        print("Copia demo1.mp4 en data/videos en el host.")
        return 1
    from app.analyze import load_model
    from app.config import load_settings

    settings = load_settings()
    model = load_model(settings.model_path)
    written = extract(video, model, directory)
    print(f"Cuadros anotados: {written}")
    print(f"Carpeta: {directory}")
    if written < MIN_FRAMES:
        print(f"Se necesitan al menos {MIN_FRAMES}.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
