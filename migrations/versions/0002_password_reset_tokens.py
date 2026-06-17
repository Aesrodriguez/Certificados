"""add password reset tokens

Revision ID: a3f1b2c4d5e6
Revises: 45750400216c
Create Date: 2026-06-16 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f1b2c4d5e6"
down_revision: Union[str, None] = "45750400216c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extend the audit action enum with new values.
    # PostgreSQL does not allow removing enum values, so downgrade leaves them.
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'password_reset_requested'")
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'password_reset_completed'")

    op.create_table(
        "password_reset_tokens",
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_reset_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_password_reset_tokens_token_hash"),
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_password_reset_tokens_user_id"),
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_index(
        op.f("ix_password_reset_tokens_token_hash"), table_name="password_reset_tokens"
    )
    op.drop_table("password_reset_tokens")
    # Note: PostgreSQL does not support removing enum values.
    # The 'password_reset_requested' and 'password_reset_completed' values
    # remain in audit_action_enum after downgrade — they are harmless.
