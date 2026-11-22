"""Consecutivo automático del N.º de documento e imágenes de marca

- Secuencia consecutivo_certificado_seq: empieza en 50000 (o después del mayor
  número numérico ya guardado, si alguno es >= 50000).
- Tabla imagenes_marca para el sello, membrete y firma cargados desde Configuración.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None

INICIO = 50000


def upgrade() -> None:
    bind = op.get_bind()
    mayor = bind.execute(sa.text(
        "SELECT max(numero_certificado::bigint) FROM certificate_requests "
        "WHERE numero_certificado ~ '^[0-9]{1,7}$'"
    )).scalar()
    inicio = max(INICIO, (mayor or 0) + 1)
    op.execute(f"CREATE SEQUENCE IF NOT EXISTS consecutivo_certificado_seq START WITH {inicio}")

    op.create_table(
        "imagenes_marca",
        sa.Column("clave", sa.String(50), primary_key=True),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("datos", sa.LargeBinary(), nullable=False),
        sa.Column("nombre_archivo", sa.String(255), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("imagenes_marca")
    op.execute("DROP SEQUENCE IF EXISTS consecutivo_certificado_seq")
