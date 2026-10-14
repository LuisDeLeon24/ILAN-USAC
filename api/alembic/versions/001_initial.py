"""Initial schema.

Revision ID: 001_initial
Revises:
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    ]


def org_column() -> sa.Column:
    return sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        *timestamps(),
    )
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        *timestamps(),
        sa.CheckConstraint("role in ('admin', 'operator')", name="ck_users_role"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_table(
        "sites",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(500)),
        *timestamps(),
    )
    op.create_index("ix_sites_organization_id", "sites", ["organization_id"])
    op.create_table(
        "cameras",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("site_id", UUID, sa.ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("rtsp_url_encrypted", sa.Text()),
        sa.Column("file_path", sa.String(500)),
        sa.Column("fps", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.CheckConstraint("source_type in ('rtsp', 'file')", name="ck_cameras_source_type"),
        sa.CheckConstraint("fps >= 2 AND fps <= 5", name="ck_cameras_fps"),
    )
    op.create_index("ix_cameras_organization_id", "cameras", ["organization_id"])
    op.create_index("ix_cameras_site_id", "cameras", ["site_id"])
    op.create_table(
        "zones",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("camera_id", UUID, sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("polygon", JSON, nullable=False),
        sa.Column("schedule", JSON, nullable=False),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("rule_params", JSON, nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "rule_type in ('intrusion', 'after_hours', 'loitering', 'occupancy')",
            name="ck_zones_rule_type",
        ),
    )
    op.create_index("ix_zones_organization_id", "zones", ["organization_id"])
    op.create_index("ix_zones_camera_id", "zones", ["camera_id"])
    op.create_table(
        "sensors",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("site_id", UUID, sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sensor_type", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(200)),
        *timestamps(),
        sa.CheckConstraint("sensor_type in ('door', 'motion', 'smoke', 'panic')", name="ck_sensors_sensor_type"),
    )
    op.create_index("ix_sensors_organization_id", "sensors", ["organization_id"])
    op.create_index("ix_sensors_site_id", "sensors", ["site_id"])
    op.create_table(
        "events",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("camera_id", UUID, sa.ForeignKey("cameras.id", ondelete="SET NULL")),
        sa.Column("sensor_id", UUID, sa.ForeignKey("sensors.id", ondelete="SET NULL")),
        sa.Column("zone_id", UUID, sa.ForeignKey("zones.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("occurred_at", TS, nullable=False),
        sa.Column("snapshot_key", sa.Text()),
        sa.Column("cooldown_key", sa.String(200)),
        *timestamps(),
        sa.CheckConstraint("severity in ('low', 'medium', 'high', 'critical')", name="ck_events_severity"),
        sa.CheckConstraint(
            "status in ('new', 'in_review', 'resolved', 'false_positive')",
            name="ck_events_status",
        ),
    )
    op.create_index("ix_events_organization_id", "events", ["organization_id"])
    op.create_index("ix_events_camera_id", "events", ["camera_id"])
    op.create_index("ix_events_sensor_id", "events", ["sensor_id"])
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"])
    op.create_table(
        "alert_contacts",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
    )
    op.create_index("ix_alert_contacts_organization_id", "alert_contacts", ["organization_id"])
    op.create_table(
        "alert_logs",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("event_id", UUID, sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alert_contact_id", UUID, sa.ForeignKey("alert_contacts.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("sent_at", TS),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_alert_logs_organization_id", "alert_logs", ["organization_id"])
    op.create_index("ix_alert_logs_event_id", "alert_logs", ["event_id"])
    op.create_table(
        "usage_records",
        sa.Column("id", UUID, primary_key=True),
        org_column(),
        sa.Column("camera_id", UUID, sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("analyzed_minutes", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("camera_id", "usage_date", name="uq_usage_records_camera_date"),
    )
    op.create_index("ix_usage_records_organization_id", "usage_records", ["organization_id"])
    op.create_index("ix_usage_records_camera_id", "usage_records", ["camera_id"])
    op.create_table(
        "pricing_plans",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("rate_per_minute", sa.Numeric(12, 4), nullable=False),
        sa.Column("setup_fee", sa.Numeric(12, 2), nullable=False),
        *timestamps(),
    )


def downgrade() -> None:
    for name in (
        "pricing_plans",
        "usage_records",
        "alert_logs",
        "alert_contacts",
        "events",
        "sensors",
        "zones",
        "cameras",
        "sites",
        "users",
        "organizations",
    ):
        op.drop_table(name)
