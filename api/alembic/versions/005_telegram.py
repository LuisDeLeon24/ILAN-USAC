"""Alert contacts can be WhatsApp or Telegram.

Revision ID: 005_telegram
Revises: 004_alerts
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_telegram"
down_revision: str | None = "004_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alert_contacts",
        sa.Column("channel", sa.String(length=16), nullable=False, server_default="whatsapp"),
    )
    op.add_column("alert_contacts", sa.Column("chat_id", sa.String(length=32), nullable=True))
    op.alter_column("alert_contacts", "phone", existing_type=sa.String(length=32), nullable=True)
    op.create_check_constraint(
        "ck_alert_contacts_channel",
        "alert_contacts",
        "(channel = 'whatsapp' AND phone IS NOT NULL AND chat_id IS NULL) OR "
        "(channel = 'telegram' AND chat_id IS NOT NULL AND phone IS NULL)",
    )
    op.create_index(
        "uq_alert_contacts_organization_chat_id",
        "alert_contacts",
        ["organization_id", "chat_id"],
        unique=True,
        postgresql_where=sa.text("chat_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_alert_contacts_organization_chat_id", table_name="alert_contacts")
    op.drop_constraint("ck_alert_contacts_channel", "alert_contacts", type_="check")
    op.execute("DELETE FROM alert_contacts WHERE channel = 'telegram'")
    op.alter_column("alert_contacts", "phone", existing_type=sa.String(length=32), nullable=False)
    op.drop_column("alert_contacts", "chat_id")
    op.drop_column("alert_contacts", "channel")
