"""Corrige el arranque del consecutivo

Si alguna solicitud tenía una cédula escrita en N.º documento (número de más de
7 cifras igual a la cédula del titular o del fallecido), la 0014 la tomaba como
el consecutivo más alto. Aquí:
- la más antigua de esas solicitudes recibe el 50000 (primera del consecutivo
  nuevo) si ese número no está usado; las demás quedan sin número;
- la secuencia sigue después del mayor número de hasta 7 cifras, mínimo 50000.
Solo actúa si la secuencia quedó en un valor de más de 7 cifras.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

INICIO = 50000
_ES_CEDULA = (
    "numero_certificado ~ '^[0-9]{8,15}$' AND "
    "(numero_certificado = regexp_replace(coalesce(cliente_numero_documento, ''), '[^0-9]', '', 'g') OR "
    " numero_certificado = regexp_replace(coalesce(fallecido_numero_documento, ''), '[^0-9]', '', 'g'))"
)


def upgrade() -> None:
    bind = op.get_bind()
    actual = bind.execute(sa.text(
        "SELECT CASE WHEN is_called THEN last_value + 1 ELSE last_value END "
        "FROM consecutivo_certificado_seq"
    )).scalar()
    if actual is None or actual <= 9_999_999:
        return

    ids = bind.execute(sa.text(
        f"SELECT id FROM certificate_requests WHERE {_ES_CEDULA} ORDER BY created_at"
    )).scalars().all()
    usado = bind.execute(sa.text(
        "SELECT 1 FROM certificate_requests WHERE numero_certificado = :n"
    ), {"n": str(INICIO)}).first()
    for i, cert_id in enumerate(ids):
        nuevo = str(INICIO) if i == 0 and not usado else None
        bind.execute(sa.text(
            "UPDATE certificate_requests SET numero_certificado = :n WHERE id = :id"
        ), {"n": nuevo, "id": cert_id})

    mayor = bind.execute(sa.text(
        "SELECT max(numero_certificado::bigint) FROM certificate_requests "
        "WHERE numero_certificado ~ '^[0-9]{1,7}$'"
    )).scalar()
    siguiente = max(INICIO, (mayor or 0) + 1)
    bind.execute(sa.text("SELECT setval('consecutivo_certificado_seq', :v, false)"), {"v": siguiente})


def downgrade() -> None:
    pass
