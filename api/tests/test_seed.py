import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.entities import AlertContact, Camera, Device, Event, Organization, PricingPlan, Sensor, Site, UsageRecord
from app.services.agent.dates import GUATEMALA, resolve_window
from app.services.demo_seed import (
    DEMO_PHONE,
    DEMO_RATE,
    EVENTS,
    deletion_lines,
    insert_demo,
    DAILY_MINUTES,
    minutes_for,
    minutes_on,
    planned_events,
    usage_dates,
)
from app.seed import main
from tests.conftest import purge_organization
from tests.test_device import JPEG


def test_catalog_on_a_thursday_has_variety_and_answers_the_demo_questions() -> None:
    moment = datetime(2026, 10, 1, 21, 0, tzinfo=GUATEMALA)
    rows = planned_events(moment)
    assert len(rows) == len(EVENTS)
    assert len(rows) >= 30
    assert {row.event_type for row in rows} >= {
        "intrusion",
        "after_hours",
        "loitering",
        "occupancy",
        "camera_disconnected",
        "door_open",
        "motion",
        "smoke",
    }
    assert {row.severity for row in rows} == {"low", "medium", "high", "critical"}
    assert {row.status for row in rows} == {"new", "in_review", "resolved", "false_positive"}
    week_start, week_end = resolve_window("this_week", None, None, moment)
    yesterday_start, yesterday_end = resolve_window("yesterday", None, None, moment)
    intrusions = [
        row
        for row in rows
        if row.event_type == "intrusion" and week_start <= row.occurred_at < week_end
    ]
    critical = [
        row
        for row in rows
        if row.severity == "critical" and yesterday_start <= row.occurred_at < yesterday_end
    ]
    assert len(intrusions) >= 1
    assert len(critical) == 1
    assert critical[0].event_type == "smoke"
    assert sum(1 for row in rows if row.snapshot) >= 8
    assert all(row.reviewed_at is None for row in rows if row.status in {"new", "false_positive"})
    assert all(row.reviewed_at is not None for row in rows if row.status in {"in_review", "resolved"})


def test_usage_covers_the_open_month_and_last_month_only_at_the_start() -> None:
    first = datetime(2026, 10, 1, 21, 0, tzinfo=GUATEMALA)
    opening = usage_dates(first)
    assert opening[0] == date(2026, 9, 1)
    assert opening[-1] == date(2026, 10, 1)
    assert len(opening) == 31
    third = usage_dates(datetime(2026, 10, 3, 8, 0, tzinfo=GUATEMALA))
    assert third[0] == date(2026, 9, 1)
    assert third[-1] == date(2026, 10, 3)
    fourth = usage_dates(datetime(2026, 10, 4, 8, 0, tzinfo=GUATEMALA))
    assert fourth == [date(2026, 10, day) for day in range(1, 5)]
    new_year = usage_dates(datetime(2026, 1, 2, 12, 0, tzinfo=GUATEMALA))
    assert new_year[0] == date(2025, 12, 1)
    assert new_year[-1] == date(2026, 1, 2)


def test_reset_refuses_without_the_flag(capsys) -> None:
    assert main([]) == 2
    assert "--reset" in capsys.readouterr().out


def test_reset_stops_before_delete_when_frames_are_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SEED_DIR", str(tmp_path))

    def boom(_db):
        raise AssertionError("wiped")

    monkeypatch.setattr("app.seed.wipe_all", boom)
    assert main(["--reset"]) == 1


def test_insert_demo_is_a_disabled_week_with_distinct_frames() -> None:
    frames = [JPEG + bytes([index]) for index in range(8)]
    stored: list[bytes] = []
    email = f"demo-{uuid.uuid4()}@example.com"
    moment = datetime(2026, 10, 1, 21, 0, tzinfo=GUATEMALA)
    organization_id = None
    db = SessionLocal()
    try:
        result = insert_demo(
            db,
            frames,
            email=email,
            password="admin12345",
            organization_name="Organización demo",
            device_token=f"seed-test-token-{uuid.uuid4().hex}",
            moment=moment,
            upload=lambda _key, payload: stored.append(payload),
            id_prefix=f"t{uuid.uuid4().hex[:12]}",
        )
        db.commit()
        organization_id = result.organization_id
        assert result.organization_name == "Organización demo"
        stored_org = db.get(Organization, organization_id)
        assert stored_org is not None
        assert stored_org.name == "Organización demo"
        cameras = db.scalars(select(Camera).where(Camera.organization_id == organization_id)).all()
        assert len(cameras) == 3
        assert {camera.loop for camera in cameras} == {False}
        assert {camera.enabled for camera in cameras} == {False}
        assert {camera.file_path for camera in cameras} == {"/videos/demo1.mp4"}
        plan = db.scalar(select(PricingPlan).where(PricingPlan.organization_id == organization_id))
        assert plan is not None
        assert DEMO_RATE == Decimal("0.005")
        assert Decimal(plan.rate_per_minute) == DEMO_RATE
        sites = {site.name: site for site in db.scalars(select(Site).where(Site.organization_id == organization_id))}
        planta = sites["Planta norte"]
        device = db.scalar(select(Device).where(Device.organization_id == organization_id))
        assert device is not None
        assert device.site_id == planta.id
        sensors = {
            sensor.external_id: sensor
            for sensor in db.scalars(select(Sensor).where(Sensor.organization_id == organization_id))
        }
        assert set(sensors) == {"puerta-norte", "movimiento-patio", "humo-planta"}
        assert sensors["puerta-norte"].sensor_type == "door"
        assert sensors["humo-planta"].sensor_type == "smoke"
        assert sensors["puerta-norte"].site_id == planta.id
        assert sensors["humo-planta"].site_id == planta.id
        assert sensors["movimiento-patio"].site_id == planta.id
        contact = db.scalar(select(AlertContact).where(AlertContact.organization_id == organization_id))
        assert contact is not None
        assert contact.phone == DEMO_PHONE
        assert contact.enabled is False
        events = db.scalar(select(func.count()).select_from(Event).where(Event.organization_id == organization_id))
        assert int(events or 0) == len(EVENTS)
        snapshots = db.scalar(
            select(func.count())
            .select_from(Event)
            .where(Event.organization_id == organization_id, Event.snapshot_key.is_not(None))
        )
        assert int(snapshots or 0) == result.snapshots
        assert set(stored) == set(frames)
        usage = db.scalar(
            select(func.count()).select_from(UsageRecord).where(UsageRecord.organization_id == organization_id)
        )
        assert int(usage or 0) == 31 * 3
        october = db.scalar(
            select(func.coalesce(func.sum(UsageRecord.analyzed_minutes), 0)).where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.usage_date >= date(2026, 10, 1),
                UsageRecord.usage_date < date(2026, 11, 1),
            )
        )
        september = db.scalar(
            select(func.coalesce(func.sum(UsageRecord.analyzed_minutes), 0)).where(
                UsageRecord.organization_id == organization_id,
                UsageRecord.usage_date >= date(2026, 9, 1),
                UsageRecord.usage_date < date(2026, 10, 1),
            )
        )
        september_days = usage_dates(moment)
        september_days = [day for day in september_days if day.month == 9]
        october_days = [day for day in usage_dates(moment) if day.month == 10]
        assert Decimal(october) == minutes_on(october_days)
        assert Decimal(september) == minutes_on(september_days)
        rows = db.execute(
            select(Camera.name, UsageRecord.usage_date, UsageRecord.analyzed_minutes)
            .join(UsageRecord, UsageRecord.camera_id == Camera.id)
            .where(UsageRecord.organization_id == organization_id)
        ).all()
        for name, usage_day, amount in rows:
            base = DAILY_MINUTES[name]
            recorded = Decimal(amount)
            assert base * Decimal("0.95") <= recorded <= base * Decimal("1.05")
            assert recorded == minutes_for(name, usage_day)
        acceso = [Decimal(amount) for name, _day, amount in rows if name == "Acceso norte"]
        assert len(set(acceso)) > 1
        lines = deletion_lines(db)
        assert any(line.endswith(" eventos") or "eventos" in line for line in lines)
    finally:
        db.close()
        if organization_id is not None:
            purge_organization(organization_id)


def test_insert_demo_rejects_too_few_frames() -> None:
    db = SessionLocal()
    try:
        with pytest.raises(ValueError):
            insert_demo(
                db,
                [JPEG],
                email=f"demo-{uuid.uuid4()}@example.com",
                password="admin12345",
                organization_name="Organización demo",
            )
        db.rollback()
    finally:
        db.close()
