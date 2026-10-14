import numpy as np

from app.frames import MAX_FRAME_WIDTH, claim_frame_upload, fit_width, select_detections
from app.rules import Detection


def person(bbox: tuple[float, float, float, float] = (0.2, 0.2, 0.5, 0.8)) -> Detection:
    return Detection(class_id=0, track_id=1, bbox=bbox)


def test_wide_frames_shrink_to_the_upload_width() -> None:
    frame = np.zeros((2160, 3840, 3), dtype=np.uint8)
    fitted = fit_width(frame)
    assert fitted.shape == (720, MAX_FRAME_WIDTH, 3)


def test_frames_already_within_the_limit_stay_the_same_size() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    assert fit_width(frame).shape == frame.shape


def test_a_frame_upload_is_claimed_once_until_the_request_clears() -> None:
    sent: set[str] = set()
    assert claim_frame_upload("cam", False, sent) is False
    assert claim_frame_upload("cam", True, sent) is True
    sent.add("cam")
    assert claim_frame_upload("cam", True, sent) is False
    assert claim_frame_upload("cam", False, sent) is False
    assert "cam" not in sent
    assert claim_frame_upload("cam", True, sent) is True


def test_small_boxes_and_exclusion_areas_are_dropped() -> None:
    small = person((0.1, 0.1, 0.12, 0.12))
    large = person((0.2, 0.2, 0.6, 0.9))
    assert select_detections([small, large], 0.05, []) == [large]
    glass = [[0.15, 0.15], [0.7, 0.15], [0.7, 0.95], [0.15, 0.95]]
    assert select_detections([large], 0, [{"polygon": glass}]) == []
    outside = person((0.0, 0.0, 0.1, 0.1))
    assert select_detections([outside], 0, [{"polygon": glass}]) == [outside]
