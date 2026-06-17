"""Add user_updated/user_deleted audit actions; audit_logs FK ON DELETE SET NULL

Revision ID: d9e4f5a6b7c8
Revises: c8d3e4f5a6b7
Create Date: 2026-06-17 00:00:00.000000
"""
from alembic import op

revision = "d9e4f5a6b7c8"
down_revision = "c8d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend the audit action enum
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'user_updated'")
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'user_deleted'")

    # Change audit_logs.actor_user_id FK to ON DELETE SET NULL so that
    # deleting a user nullifies their audit log actor references instead of blocking.
    op.drop_constraint(
        "fk_audit_logs_actor_user_id_users",
        "audit_logs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_audit_logs_actor_user_id_users",
        "audit_logs",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Restore original FK without ON DELETE SET NULL
    op.drop_constraint(
        "fk_audit_logs_actor_user_id_users",
        "audit_logs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_audit_logs_actor_user_id_users",
        "audit_logs",
        "users",
        ["actor_user_id"],
        ["id"],
    )
    # PostgreSQL does not support removing enum values; downgrade skips that step.
