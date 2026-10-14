"""Conversations, messages, and audited tool calls for the assistant.

Revision ID: 006_agent
Revises: 005_telegram
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_agent"
down_revision: str | None = "005_telegram"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSON = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pending_action", JSON, nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_agent_conversations_user"),
    )
    op.create_index("ix_agent_conversations_organization_id", "agent_conversations", ["organization_id"])
    op.create_table(
        "agent_messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("conversation_id", UUID, sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role in ('user', 'assistant')", name="ck_agent_messages_role"),
    )
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])
    op.create_index("ix_agent_messages_organization_id", "agent_messages", ["organization_id"])
    op.create_table(
        "agent_tool_calls",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", UUID, sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("arguments", JSON, nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("detail", sa.String(500), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "outcome in ('executed', 'pending_confirmation', 'rejected', 'error')",
            name="ck_agent_tool_calls_outcome",
        ),
    )
    op.create_index("ix_agent_tool_calls_organization_id", "agent_tool_calls", ["organization_id"])
    op.create_index("ix_agent_tool_calls_conversation_id", "agent_tool_calls", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_tool_calls_conversation_id", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_organization_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")
    op.drop_index("ix_agent_messages_organization_id", table_name="agent_messages")
    op.drop_index("ix_agent_messages_conversation_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_conversations_organization_id", table_name="agent_conversations")
    op.drop_table("agent_conversations")
