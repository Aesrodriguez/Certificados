"""Agrega fecha_solicitud_documento a certificate_requests

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-01
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "certificate_requests",
        sa.Column("fecha_solicitud_documento", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("certificate_requests", "fecha_solicitud_documento")
