"""Agrega configuración de campos obligatorios

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "INSERT INTO app_settings (key, value) "
        "VALUES ('required_fields', '[\"cliente_email\"]') "
        "ON CONFLICT (key) DO NOTHING"
    ))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM app_settings WHERE key = 'required_fields'"))
