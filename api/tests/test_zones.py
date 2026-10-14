import pytest
from pydantic import ValidationError

from app.schemas.cameras import CameraCreate
from app.schemas.zones import ZoneWrite


def schedule() -> dict:
    return {
        "timezone": "America/Guatemala",
        "windows": [{"days": ["mon", "fri"], "start": "08:00", "end": "18:00"}],
    }


def test_intrusion_zone_accepts_normalized_polygon() -> None:
    zone = ZoneWrite(
        name=" Bodega ",
        polygon=[[0, 0], [1, 0], [1, 1]],
        schedule=schedule(),
        rule_type="intrusion",
        rule_params={"ignored": True},
    )
    assert zone.name == "Bodega"
    assert zone.rule_params == {}


def test_loitering_requires_positive_seconds() -> None:
    with pytest.raises(ValidationError):
        ZoneWrite(
            name="Andén",
            polygon=[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]],
            schedule=schedule(),
            rule_type="loitering",
            rule_params={},
        )


def test_polygon_must_stay_inside_the_frame() -> None:
    with pytest.raises(ValidationError):
        ZoneWrite(
            name="Patio",
            polygon=[[0, 0], [1.2, 0], [1, 1]],
            schedule=schedule(),
            rule_type="occupancy",
            rule_params={"max_people": 3},
        )


def test_schedule_rejects_an_end_before_the_start() -> None:
    with pytest.raises(ValidationError):
        ZoneWrite(
            name="Turno",
            polygon=[[0, 0], [1, 0], [0.5, 1]],
            schedule={
                "timezone": "America/Guatemala",
                "windows": [{"days": ["sat"], "start": "18:00", "end": "08:00"}],
            },
            rule_type="after_hours",
        )


def test_camera_requires_an_rtsp_scheme() -> None:
    with pytest.raises(ValidationError):
        CameraCreate(site_id="00000000-0000-0000-0000-000000000001", name="Portería", source_type="rtsp", rtsp_url="http://cam")
