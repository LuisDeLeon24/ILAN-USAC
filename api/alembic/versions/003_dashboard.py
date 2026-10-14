"""Detection settings, exclusion areas, event review time, and editor frames.

Revision ID: 003_dashboard
Revises: 002_devices
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_dashboard"
down_revision: str | None = "002_devices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("cameras", sa.Column("min_confidence", sa.Numeric(4, 2), nullable=False, server_default="0.35"))
    op.add_column("cameras", sa.Column("min_box_area", sa.Numeric(6, 4), nullable=False, server_default="0"))
    op.add_column("cameras", sa.Column("frame_requested", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("cameras", sa.Column("preview_key", sa.Text()))
    op.add_column("cameras", sa.Column("preview_at", TS))
    op.create_check_constraint(
        "ck_cameras_min_confidence",
        "cameras",
        "min_confidence >= 0.05 AND min_confidence <= 0.95",
    )
    op.create_check_constraint("ck_cameras_min_box_area", "cameras", "min_box_area >= 0 AND min_box_area <= 1")
    op.add_column("events", sa.Column("reviewed_at", TS))
    op.create_table(
        "exclusion_areas",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_id", UUID, sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("polygon", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_exclusion_areas_organization_id", "exclusion_areas", ["organization_id"])
    op.create_index("ix_exclusion_areas_camera_id", "exclusion_areas", ["camera_id"])


def downgrade() -> None:
    op.drop_index("ix_exclusion_areas_camera_id", table_name="exclusion_areas")
    op.drop_index("ix_exclusion_areas_organization_id", table_name="exclusion_areas")
    op.drop_table("exclusion_areas")
    op.drop_column("events", "reviewed_at")
    op.drop_constraint("ck_cameras_min_box_area", "cameras", type_="check")
    op.drop_constraint("ck_cameras_min_confidence", "cameras", type_="check")
    op.drop_column("cameras", "preview_at")
    op.drop_column("cameras", "preview_key")
    op.drop_column("cameras", "frame_requested")
    op.drop_column("cameras", "min_box_area")
    op.drop_column("cameras", "min_confidence")
