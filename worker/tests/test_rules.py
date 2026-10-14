from datetime import datetime
from zoneinfo import ZoneInfo

from app.rules import Cooldown, Detection, evaluate, point_in_polygon, schedule_is_active

GUATEMALA = ZoneInfo("America/Guatemala")
POLYGON = [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]
INSIDE = (0.4, 0.3, 0.6, 0.6)
OUTSIDE = (0.0, 0.0, 0.1, 0.1)
BUSINESS = {
    "timezone": "America/Guatemala",
    "windows": [{"days": ["mon", "tue", "wed", "thu", "fri"], "start": "08:00", "end": "18:00"}],
}
ALL_DAY = {
    "timezone": "America/Guatemala",
    "windows": [{"days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "start": "00:00", "end": "23:59"}],
}
THURSDAY_NOON = datetime(2026, 10, 1, 12, 0, tzinfo=GUATEMALA)
THURSDAY_NIGHT = datetime(2026, 10, 1, 20, 0, tzinfo=GUATEMALA)
THURSDAY_OPEN = datetime(2026, 10, 1, 8, 0, tzinfo=GUATEMALA)
THURSDAY_CLOSE = datetime(2026, 10, 1, 18, 0, tzinfo=GUATEMALA)
SUNDAY_NOON = datetime(2026, 10, 4, 12, 0, tzinfo=GUATEMALA)
SUNDAY_LATE = datetime(2026, 10, 4, 23, 50, tzinfo=GUATEMALA)


def person(track_id: int = 1, bbox: tuple[float, float, float, float] = INSIDE) -> Detection:
    return Detection(class_id=0, track_id=track_id, bbox=bbox)


def zone(rule_type: str, schedule: dict | None = None, **params) -> dict:
    return {
        "id": "zone-1",
        "rule_type": rule_type,
        "polygon": POLYGON,
        "schedule": schedule or BUSINESS,
        "rule_params": params,
    }


def hits(**kwargs):
    defaults = {
        "camera_id": "cam-1",
        "zones": [zone("intrusion")],
        "detections": [person()],
        "moment": THURSDAY_NOON,
        "video_time": 0,
        "dwell": {},
        "cooldown": Cooldown(),
        "cooldown_seconds": 60,
        "now": 0,
    }
    defaults.update(kwargs)
    return evaluate(**defaults)


def test_point_in_polygon_uses_the_interior() -> None:
    assert point_in_polygon(0.5, 0.5, POLYGON)
    assert not point_in_polygon(0.05, 0.05, POLYGON)


def test_business_hours_start_is_inclusive_and_end_is_exclusive() -> None:
    assert schedule_is_active(BUSINESS, THURSDAY_OPEN)
    assert not schedule_is_active(BUSINESS, THURSDAY_CLOSE)


def test_full_day_window_includes_the_last_minute() -> None:
    assert schedule_is_active(ALL_DAY, SUNDAY_LATE)


def test_intrusion_fires_when_a_person_is_inside_while_the_rule_is_armed() -> None:
    found = hits()
    assert [item.event_type for item in found] == ["intrusion"]


def test_intrusion_does_not_fire_outside_the_zone_while_armed() -> None:
    assert hits(detections=[person(bbox=OUTSIDE)]) == []


def test_intrusion_does_not_fire_when_the_schedule_is_not_armed() -> None:
    assert hits(moment=THURSDAY_NIGHT) == []


def test_intrusion_is_not_armed_on_a_closed_day() -> None:
    assert hits(moment=SUNDAY_NOON) == []


def test_intrusion_is_armed_for_the_full_day_schedule() -> None:
    found = hits(zones=[zone("intrusion", ALL_DAY)], moment=SUNDAY_LATE)
    assert [item.event_type for item in found] == ["intrusion"]


def test_after_hours_fires_outside_allowed_business_hours() -> None:
    found = hits(zones=[zone("after_hours")], moment=THURSDAY_NIGHT)
    assert [item.event_type for item in found] == ["after_hours"]


def test_after_hours_does_not_fire_during_allowed_business_hours() -> None:
    assert hits(zones=[zone("after_hours")], moment=THURSDAY_NOON) == []


def test_after_hours_fires_on_a_closed_day() -> None:
    found = hits(zones=[zone("after_hours")], moment=SUNDAY_NOON)
    assert [item.event_type for item in found] == ["after_hours"]


def test_after_hours_does_not_fire_during_a_full_day_schedule() -> None:
    assert hits(zones=[zone("after_hours", ALL_DAY)], moment=SUNDAY_LATE) == []


def test_after_hours_ignores_a_person_outside_the_zone() -> None:
    assert hits(zones=[zone("after_hours")], detections=[person(bbox=OUTSIDE)], moment=THURSDAY_NIGHT) == []


def test_loitering_fires_after_the_armed_duration() -> None:
    dwell: dict[tuple[str, int], float] = {}
    cooldown = Cooldown()
    shared = {"zones": [zone("loitering", seconds=30)], "dwell": dwell, "cooldown": cooldown, "moment": THURSDAY_NOON}
    assert hits(video_time=0, **shared) == []
    found = hits(video_time=30, now=30, **shared)
    assert [item.event_type for item in found] == ["loitering"]


def test_loitering_does_not_accumulate_while_the_rule_is_disarmed() -> None:
    dwell: dict[tuple[str, int], float] = {}
    hits(zones=[zone("loitering", seconds=30)], moment=THURSDAY_NIGHT, video_time=100, dwell=dwell)
    assert dwell == {}


def test_occupancy_fires_only_above_the_maximum_while_armed() -> None:
    people = [person(1), person(2, (0.45, 0.3, 0.55, 0.7))]
    assert hits(zones=[zone("occupancy", max_people=1)], detections=[person()]) == []
    found = hits(zones=[zone("occupancy", max_people=1)], detections=people)
    assert [item.event_type for item in found] == ["occupancy"]
    assert hits(zones=[zone("occupancy", max_people=1)], detections=people, moment=THURSDAY_NIGHT) == []


def test_vehicles_do_not_fire_person_rules() -> None:
    vehicle = Detection(class_id=2, track_id=4, bbox=INSIDE)
    assert hits(detections=[vehicle]) == []
    assert hits(zones=[zone("after_hours")], detections=[vehicle], moment=THURSDAY_NIGHT) == []


def test_cooldown_suppresses_a_repeat_until_the_window_passes() -> None:
    cooldown = Cooldown()
    assert len(hits(cooldown=cooldown, now=100)) == 1
    assert hits(cooldown=cooldown, now=120) == []
    assert len(hits(cooldown=cooldown, now=160)) == 1
