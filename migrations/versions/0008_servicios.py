"""Servicios — tabla de plantillas de desglose de servicios con seed inicial

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-08-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "servicios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("empresa_key", sa.String(100), nullable=False, server_default=""),
        sa.Column("servicio_key", sa.String(200), nullable=False, server_default=""),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_servicios"),
    )

    op.create_table(
        "servicio_lineas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("servicio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(300), nullable=False),
        sa.Column("porcentaje", sa.Float(), nullable=False),
        sa.Column("orden_linea", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_servicio_lineas"),
        sa.ForeignKeyConstraint(
            ["servicio_id"],
            ["servicios.id"],
            name="fk_servicio_lineas_servicio_id_servicios",
            ondelete="CASCADE",
        ),
    )

    _seed(op.get_bind())


def downgrade() -> None:
    op.drop_table("servicio_lineas")
    op.drop_table("servicios")


# ── Seed data ────────────────────────────────────────────────────────────────

def _seed(conn) -> None:
    import uuid as _uuid
    from sqlalchemy import text

    def _pyf_std(cofre_nombre: str) -> list:
        return [
            ("Recogida del cuerpo dentro del perímetro urbano", 0.04),
            ("Preparación normal del cuerpo", 0.09),
            (cofre_nombre, 0.41),
            ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.03),
            ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
            ("Cafeteria (Bebidas calientes en sala)", 0.05),
            ("Carteles Virtuales", 0.01),
            ("Trámites civiles y legales ante autoridad competente (Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
            ("Velación normal (24 horas)", 0.31),
        ]

    servicios = [
        {
            "nombre": "RECORDAR — Transporte, Velación y Misa",
            "empresa_key": "recordar",
            "servicio_key": "transporte velacion misa",
            "orden": 1,
            "lineas": [
                ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.50),
                ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.04),
                ("Cafeteria (Bebidas calientes en sala)", 0.05),
                ("Carteles Virtuales", 0.01),
                ("Velación por 24 horas", 0.40),
            ],
        },
        {
            "nombre": "RECORDAR — Transporte y Velación",
            "empresa_key": "recordar",
            "servicio_key": "transporte velacion",
            "orden": 2,
            "lineas": [
                ("Traslado terrestre de la persona fallecida al parque cementerio Jardines de Eternidad sede norte", 0.30),
                ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.22),
                ("Cafeteria (Bebidas calientes en sala)", 0.05),
                ("Carteles Virtuales", 0.01),
                ("Velación por 24 horas", 0.42),
            ],
        },
        {
            "nombre": "RECORDAR — Servicio Funerario Estándar",
            "empresa_key": "recordar",
            "servicio_key": "",
            "orden": 3,
            "lineas": [
                ("Traslado del cuerpo dentro del perímetro urbano", 0.04),
                ("Preparación normal del cuerpo", 0.09),
                ("Suministro del féretro según la Alternativa seleccionada", 0.41),
                ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.03),
                ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
                ("Cafeteria (Bebidas calientes en sala)", 0.05),
                ("Carteles Virtuales", 0.01),
                ("Trámites civiles y legales ante autoridad competente (Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
                ("Velación por 24 horas", 0.31),
            ],
        },
        {
            "nombre": "PARQUES Y FUNERARIAS — Cremación",
            "empresa_key": "parques",
            "servicio_key": "cremacion",
            "orden": 4,
            "lineas": [
                ("Recogida del cuerpo dentro del perímetro urbano", 0.04),
                ("Preparación normal del cuerpo", 0.09),
                ('Cofre funebre "L" o el equivalente a talla y peso del fallecido', 0.41),
                ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.03),
                ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
                ("Cafeteria (Bebidas calientes en sala)", 0.05),
                ("Carteles Virtuales", 0.01),
                ("Trámites civiles y legales ante autoridad competente (Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
                ("Velación normal (24 horas)", 0.21),
                ("Reducción del cuerpo a Cenizas por medio del calor", 0.10),
            ],
        },
        {
            "nombre": "PARQUES Y FUNERARIAS — Gran Extra",
            "empresa_key": "parques",
            "servicio_key": "gran extra",
            "orden": 5,
            "lineas": _pyf_std('Cofre funebre "Gran Extra" o el equivalente a talla y peso del fallecido'),
        },
        {
            "nombre": "PARQUES Y FUNERARIAS — Estilo J",
            "empresa_key": "parques",
            "servicio_key": "estilo j",
            "orden": 6,
            "lineas": _pyf_std('Cofre funebre "J" o el equivalente a talla y peso del fallecido'),
        },
        {
            "nombre": "PARQUES Y FUNERARIAS — Estilo K",
            "empresa_key": "parques",
            "servicio_key": "estilo k",
            "orden": 7,
            "lineas": _pyf_std('Cofre funebre "K" o el equivalente a talla y peso del fallecido'),
        },
        {
            "nombre": "PARQUES Y FUNERARIAS — Estilo L",
            "empresa_key": "parques",
            "servicio_key": "estilo l",
            "orden": 8,
            "lineas": _pyf_std('Cofre funebre "L" o el equivalente a talla y peso del fallecido'),
        },
        {
            "nombre": "PARQUES Y FUNERARIAS — Estándar",
            "empresa_key": "parques",
            "servicio_key": "",
            "orden": 9,
            "lineas": _pyf_std("Cofre funebre según la Alternativa seleccionada"),
        },
    ]

    for svc in servicios:
        svc_id = str(_uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO servicios (id, nombre, empresa_key, servicio_key, orden, is_active, created_at, updated_at) "
                "VALUES (:id, :nombre, :empresa_key, :servicio_key, :orden, true, NOW(), NOW())"
            ),
            {
                "id": svc_id,
                "nombre": svc["nombre"],
                "empresa_key": svc["empresa_key"],
                "servicio_key": svc["servicio_key"],
                "orden": svc["orden"],
            },
        )
        for i, (linea_nombre, linea_pct) in enumerate(svc["lineas"]):
            conn.execute(
                text(
                    "INSERT INTO servicio_lineas (id, servicio_id, nombre, porcentaje, orden_linea) "
                    "VALUES (:id, :servicio_id, :nombre, :porcentaje, :orden_linea)"
                ),
                {
                    "id": str(_uuid.uuid4()),
                    "servicio_id": svc_id,
                    "nombre": linea_nombre,
                    "porcentaje": linea_pct,
                    "orden_linea": i,
                },
            )
