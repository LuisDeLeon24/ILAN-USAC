import cv2
import numpy as np


def test_opencv_opens_a_generated_video(tmp_path) -> None:
    path = tmp_path / "tiny.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 2.0, (32, 32))
    assert writer.isOpened()
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    writer.write(frame)
    writer.release()

    capture = cv2.VideoCapture(str(path))
    try:
        assert capture.isOpened()
        ok, read = capture.read()
    finally:
        capture.release()
    assert ok
    assert read is not None
    assert read.shape == (32, 32, 3)
