"""Zone rules.

A schedule is when the rule is armed. A full-day window (00:00 to 23:59, every day)
keeps the rule armed all day.

Intrusion, loitering, and occupancy fire only while that schedule is active.
After hours uses the same windows as allowed business hours and fires when a person
is inside the zone outside those windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

PERSON_CLASS = 0
VEHICLE_CLASSES = frozenset({2, 3, 5, 7})
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True)
class Detection:
    class_id: int
    track_id: int | None
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class Hit:
    zone_id: str
    event_type: str
    cooldown_key: str


class Cooldown:
    def __init__(self) -> None:
        self.seen: dict[str, float] = {}

    def allow(self, key: str, now: float, seconds: float) -> bool:
        last = self.seen.get(key)
        if last is not None and now - last < seconds:
            return False
        self.seen[key] = now
        return True


def foot_point(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, _y1, x2, y2 = bbox
    return ((x1 + x2) / 2, y2)


def point_in_polygon(x: float, y: float, polygon: list) -> bool:
    if len(polygon) < 3:
        return False
    inside = False
    previous = len(polygon) - 1
    for index, point in enumerate(polygon):
        xi, yi = float(point[0]), float(point[1])
        xj, yj = float(polygon[previous][0]), float(polygon[previous][1])
        crosses = (yi > y) != (yj > y)
        if crosses and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        previous = index
    return inside


def schedule_is_active(schedule: dict, moment: datetime) -> bool:
    """True when the local time falls inside a schedule window.

    A window that ends at 23:59 covers the rest of that day, so 00:00–23:59 is the full day.
    Any other end is exclusive.
    """
    local = moment.astimezone(ZoneInfo(schedule.get("timezone") or "America/Guatemala"))
    day = WEEKDAYS[local.weekday()]
    clock = f"{local.hour:02d}:{local.minute:02d}"
    for window in schedule.get("windows") or []:
        if day not in (window.get("days") or []):
            continue
        start = window["start"]
        end = window["end"]
        if end == "23:59":
            if start <= clock <= "23:59":
                return True
        elif start <= clock < end:
            return True
    return False


def _people_inside(detections: list[Detection], polygon: list) -> list[Detection]:
    found: list[Detection] = []
    for detection in detections:
        if detection.class_id != PERSON_CLASS:
            continue
        x_coord, y_coord = foot_point(detection.bbox)
        if point_in_polygon(x_coord, y_coord, polygon):
            found.append(detection)
    return found


def _forget_zone(dwell: dict[tuple[str, int], float], zone_id: str) -> None:
    for key in list(dwell):
        if key[0] == zone_id:
            del dwell[key]


def _record(hits: list[Hit], cooldown: Cooldown, key: str, zone_id: str, event_type: str, now: float, seconds: float) -> None:
    if cooldown.allow(key, now, seconds):
        hits.append(Hit(zone_id=zone_id, event_type=event_type, cooldown_key=key))


def evaluate(
    *,
    camera_id: str,
    zones: list[dict],
    detections: list[Detection],
    moment: datetime,
    video_time: float,
    dwell: dict[tuple[str, int], float],
    cooldown: Cooldown,
    cooldown_seconds: float,
    now: float,
) -> list[Hit]:
    hits: list[Hit] = []
    for zone in zones:
        zone_id = str(zone["id"])
        rule_type = zone["rule_type"]
        polygon = zone["polygon"]
        armed = schedule_is_active(zone["schedule"], moment)
        watching = (not armed) if rule_type == "after_hours" else armed
        if not watching:
            _forget_zone(dwell, zone_id)
            continue
        people = _people_inside(detections, polygon)
        if rule_type == "intrusion":
            if people:
                _record(hits, cooldown, f"{camera_id}:{zone_id}:intrusion", zone_id, "intrusion", now, cooldown_seconds)
        elif rule_type == "after_hours":
            if people:
                _record(
                    hits, cooldown, f"{camera_id}:{zone_id}:after_hours", zone_id, "after_hours", now, cooldown_seconds
                )
        elif rule_type == "occupancy":
            max_people = zone.get("rule_params", {}).get("max_people")
            if isinstance(max_people, int) and not isinstance(max_people, bool) and len(people) > max_people:
                _record(hits, cooldown, f"{camera_id}:{zone_id}:occupancy", zone_id, "occupancy", now, cooldown_seconds)
        elif rule_type == "loitering":
            seconds = zone.get("rule_params", {}).get("seconds")
            if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
                continue
            seen: set[int] = set()
            triggered = False
            for person in people:
                if person.track_id is None:
                    continue
                seen.add(person.track_id)
                started = dwell.setdefault((zone_id, person.track_id), video_time)
                if video_time - started >= seconds:
                    triggered = True
            for key in list(dwell):
                if key[0] == zone_id and key[1] not in seen:
                    del dwell[key]
            if triggered:
                _record(hits, cooldown, f"{camera_id}:{zone_id}:loitering", zone_id, "loitering", now, cooldown_seconds)
    return hits
