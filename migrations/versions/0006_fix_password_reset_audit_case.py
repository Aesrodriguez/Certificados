"""Fix password_reset audit action case: normalize uppercase rows to lowercase

Revision ID: e1f2a3b4c5d6
Revises: d9e4f5a6b7c8
Create Date: 2026-06-17 02:00:00.000000

Migration 0003 added uppercase 'PASSWORD_RESET_REQUESTED' / 'PASSWORD_RESET_COMPLETED'
to the audit_action_enum because the Python AuditActionEnum members used uppercase
string values.  This migration corrects the Python enum to use the lowercase values
(added in 0002) and updates any existing rows so the data stays consistent.
PostgreSQL does not support removing enum values, so the uppercase variants remain
in the type definition but are no longer used.
"""
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d9e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE audit_logs SET action = 'password_reset_requested' "
        "WHERE action = 'PASSWORD_RESET_REQUESTED'"
    )
    op.execute(
        "UPDATE audit_logs SET action = 'password_reset_completed' "
        "WHERE action = 'PASSWORD_RESET_COMPLETED'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE audit_logs SET action = 'PASSWORD_RESET_REQUESTED' "
        "WHERE action = 'password_reset_requested'"
    )
    op.execute(
        "UPDATE audit_logs SET action = 'PASSWORD_RESET_COMPLETED' "
        "WHERE action = 'password_reset_completed'"
    )
