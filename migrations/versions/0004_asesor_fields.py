"""Add asesor dashboard fields to certificate_requests

Revision ID: c8d3e4f5a6b7
Revises: b7c2d3e4f5a6
Create Date: 2026-06-16 00:00:00.000000

Adds the fields used in the Asesor dashboard form (matching the Excel BASE sheet
and Word certificate template):
  empresa, tipo_certificado, numero_aviso, fecha_afiliacion, numero_recibo_caja,
  numero_contrato, numero_certificado, numero_factura, nombre_servicio,
  descripcion_servicio, valor_total
All new columns are nullable for backward compatibility with existing rows.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d3e4f5a6b7"
down_revision: Union[str, None] = "b7c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("certificate_requests", sa.Column("empresa", sa.String(length=100), nullable=True))
    op.add_column("certificate_requests", sa.Column("tipo_certificado", sa.String(length=100), nullable=True))
    op.add_column("certificate_requests", sa.Column("numero_aviso", sa.String(length=50), nullable=True))
    op.add_column("certificate_requests", sa.Column("fecha_afiliacion", sa.Date(), nullable=True))
    op.add_column("certificate_requests", sa.Column("numero_recibo_caja", sa.String(length=50), nullable=True))
    op.add_column("certificate_requests", sa.Column("numero_contrato", sa.String(length=100), nullable=True))
    op.add_column("certificate_requests", sa.Column("numero_certificado", sa.String(length=50), nullable=True))
    op.add_column("certificate_requests", sa.Column("numero_factura", sa.String(length=50), nullable=True))
    op.add_column("certificate_requests", sa.Column("nombre_servicio", sa.String(length=255), nullable=True))
    op.add_column("certificate_requests", sa.Column("descripcion_servicio", sa.String(length=255), nullable=True))
    op.add_column("certificate_requests", sa.Column("valor_total", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("certificate_requests", "valor_total")
    op.drop_column("certificate_requests", "descripcion_servicio")
    op.drop_column("certificate_requests", "nombre_servicio")
    op.drop_column("certificate_requests", "numero_factura")
    op.drop_column("certificate_requests", "numero_certificado")
    op.drop_column("certificate_requests", "numero_contrato")
    op.drop_column("certificate_requests", "numero_recibo_caja")
    op.drop_column("certificate_requests", "fecha_afiliacion")
    op.drop_column("certificate_requests", "numero_aviso")
    op.drop_column("certificate_requests", "tipo_certificado")
    op.drop_column("certificate_requests", "empresa")
