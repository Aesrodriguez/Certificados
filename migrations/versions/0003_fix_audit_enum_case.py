"""fix audit_action_enum case for password reset values

Revision ID: b7c2d3e4f5a6
Revises: a3f1b2c4d5e6
Create Date: 2026-06-17 00:00:00.000000

Migration 0002 added enum values in lowercase ('password_reset_requested')
but all existing audit_action_enum values are uppercase ('LOGIN_SUCCESS').
SQLAlchemy uses the Python enum member name (uppercase) when storing to a
native PostgreSQL ENUM, so the lowercase values never match and cause a
DataError on insert.  This migration adds the uppercase variants.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7c2d3e4f5a6"
down_revision: Union[str, None] = "a3f1b2c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'PASSWORD_RESET_REQUESTED'"
    )
    op.execute(
        "ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'PASSWORD_RESET_COMPLETED'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    pass
