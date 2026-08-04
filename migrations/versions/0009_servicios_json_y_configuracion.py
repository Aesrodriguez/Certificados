"""Agrega servicios_json a certificate_requests y tabla app_settings

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "certificate_requests",
        sa.Column("servicios_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.String(500), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_app_settings"),
    )

    op.get_bind().execute(
        sa.text("INSERT INTO app_settings (key, value) VALUES ('email_enabled', 'false')")
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("certificate_requests", "servicios_json")
