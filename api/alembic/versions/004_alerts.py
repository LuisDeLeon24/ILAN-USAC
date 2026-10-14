"""Sensor identity and alert log test rows.

Revision ID: 004_alerts
Revises: 003_dashboard
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_alerts"
down_revision: str | None = "003_dashboard"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("UPDATE sensors SET external_id = id::text WHERE external_id IS NULL OR btrim(external_id) = ''")
    op.alter_column("sensors", "external_id", existing_type=sa.String(length=200), nullable=False)
    op.create_unique_constraint("uq_sensors_organization_external_id", "sensors", ["organization_id", "external_id"])
    op.alter_column("alert_logs", "event_id", existing_type=UUID, nullable=True)
    op.add_column("alert_logs", sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_check_constraint(
        "ck_alert_logs_status",
        "alert_logs",
        "status in ('sent', 'failed', 'suppressed')",
    )
    op.create_check_constraint(
        "ck_alert_logs_test_event",
        "alert_logs",
        "(is_test = true AND event_id IS NULL) OR (is_test = false AND event_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_alert_logs_test_event", "alert_logs", type_="check")
    op.drop_constraint("ck_alert_logs_status", "alert_logs", type_="check")
    op.drop_column("alert_logs", "is_test")
    op.alter_column("alert_logs", "event_id", existing_type=UUID, nullable=False)
    op.drop_constraint("uq_sensors_organization_external_id", "sensors", type_="unique")
    op.alter_column("sensors", "external_id", existing_type=sa.String(length=200), nullable=True)
