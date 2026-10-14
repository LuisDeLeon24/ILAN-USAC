"""Devices, camera loop, and usage idempotency.

Revision ID: 002_devices
Revises: 001_initial
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_devices"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("cameras", sa.Column("loop", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("events", sa.Column("client_event_id", sa.String(64)))
    op.create_index("uq_events_client_event_id", "events", ["client_event_id"], unique=True)
    op.create_table(
        "devices",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("site_id", UUID, sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("last_seen_at", TS),
        sa.Column("model_version", sa.String(64)),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_devices_organization_id", "devices", ["organization_id"])
    op.create_index("ix_devices_site_id", "devices", ["site_id"])
    op.create_table(
        "usage_reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", UUID, sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_report_id", sa.String(64), nullable=False, unique=True),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("analyzed_minutes", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_usage_reports_organization_id", "usage_reports", ["organization_id"])
    op.create_index("ix_usage_reports_camera_id", "usage_reports", ["camera_id"])


def downgrade() -> None:
    op.drop_table("usage_reports")
    op.drop_table("devices")
    op.drop_index("uq_events_client_event_id", table_name="events")
    op.drop_column("events", "client_event_id")
    op.drop_column("cameras", "loop")
