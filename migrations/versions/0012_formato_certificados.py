"""Formato de certificados según documento "Elaboración de Certificado"

- fecha_servicio (nueva).
- fecha de fallecimiento, teléfono, correo y parentesco pasan a ser opcionales
  (el formulario ya los permitía vacíos, pero la BD los exigía).
- Renombra los tipos de documento a los nombres del documento.
- Agrega plantillas de desglose para los servicios nuevos (porcentajes base
  estándar, editables por el admin en el módulo Servicios). No toca plantillas
  que ya existan con la misma empresa_key + servicio_key.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-16
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

_NULLABLE = ["cliente_telefono", "cliente_email", "cliente_parentesco", "fallecido_fecha_fallecimiento"]

_TIPOS_RENOMBRADOS = [
    ("CERTIFICACION DE GASTOS POR FACTURA", "CERTIFICADO DE GASTOS POR FACTURA"),
    ("CERTIFICADO DE GASTOS RECORDAR", "CERTIFICADO DE GASTOS POR SERVICIOS"),
]

# (nombre, empresa_key, servicio_key, orden, [(línea, porcentaje), ...])
_PLANTILLAS = [('RECORDAR — Servicio de Cremación',
  'recordar',
  'servicio de cremacion',
  0,
  [('Traslado del cuerpo dentro del perímetro urbano', 0.04),
   ('Preparación normal del cuerpo', 0.09),
   ('Suministro del féretro según la Alternativa seleccionada', 0.41),
   ('Traslado urbano de la persona fallecida a la sala de velación y Campo Santo', 0.0),
   ('(Carroza Funebre)', 0.03),
   ('Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)', 0.02),
   ('Cafeteria (Bebidas calientes en sala)', 0.05),
   ('Carteles Virtuales', 0.01),
   ('Trámites ante autoridades competentes', 0.0),
   ('(Licencia de inhumación o cremación- Registro de Defunción)', 0.04),
   ('Velación por 24 horas', 0.21),
   ('Reducción del cuerpo a Cenizas por medio del calor', 0.1)]),
 ('RECORDAR — Servicio Funerario Clásico',
  'recordar',
  'servicio funerario clasico',
  0,
  [('Traslado del cuerpo dentro del perímetro urbano', 0.04),
   ('Preparación normal del cuerpo', 0.09),
   ('Suministro del féretro según la Alternativa seleccionada', 0.41),
   ('Traslado urbano de la persona fallecida a la sala de velación y Campo Santo', 0.0),
   ('(Carroza Funebre)', 0.03),
   ('Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)', 0.02),
   ('Cafeteria (Bebidas calientes en sala)', 0.05),
   ('Carteles Virtuales', 0.01),
   ('Trámites ante autoridades competentes', 0.0),
   ('(Licencia de inhumación o cremación- Registro de Defunción)', 0.04),
   ('Velación por 24 horas', 0.31)]),
 ('RECORDAR — Servicio Funerario Superior',
  'recordar',
  'servicio funerario superior',
  0,
  [('Traslado del cuerpo dentro del perímetro urbano', 0.04),
   ('Preparación normal del cuerpo', 0.09),
   ('Suministro del féretro según la Alternativa seleccionada', 0.41),
   ('Traslado urbano de la persona fallecida a la sala de velación y Campo Santo', 0.0),
   ('(Carroza Funebre)', 0.03),
   ('Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)', 0.02),
   ('Cafeteria (Bebidas calientes en sala)', 0.05),
   ('Carteles Virtuales', 0.01),
   ('Trámites ante autoridades competentes', 0.0),
   ('(Licencia de inhumación o cremación- Registro de Defunción)', 0.04),
   ('Velación por 24 horas', 0.31)]),
 ('RECORDAR — Servicio Funerario Excelencia',
  'recordar',
  'servicio funerario excelencia',
  0,
  [('Traslado del cuerpo dentro del perímetro urbano', 0.04),
   ('Preparación normal del cuerpo', 0.09),
   ('Suministro del féretro según la Alternativa seleccionada', 0.41),
   ('Traslado urbano de la persona fallecida a la sala de velación y Campo Santo', 0.0),
   ('(Carroza Funebre)', 0.03),
   ('Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)', 0.02),
   ('Cafeteria (Bebidas calientes en sala)', 0.05),
   ('Carteles Virtuales', 0.01),
   ('Trámites ante autoridades competentes', 0.0),
   ('(Licencia de inhumación o cremación- Registro de Defunción)', 0.04),
   ('Velación por 24 horas', 0.31)]),
 ('PARQUES Y FUNERARIAS — Estilo Clásico',
  'parques',
  'estilo clasico',
  8,
  [('Recogida del cuerpo dentro del perímetro urbano', 0.04),
   ('Preparación normal del cuerpo', 0.09),
   ('Cofre funebre "Clásico" o el equivalente a talla y peso de fallecido', 0.41),
   ('Traslado urbano de la persona fallecida a la sala de velación y Campo Santo', 0.0),
   ('(Carroza Funebre)', 0.03),
   ('Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)', 0.02),
   ('Cafeteria (Bebidas calientes en sala)', 0.05),
   ('Carteles Virtuales', 0.01),
   ('Trámites ante autoridades competentes', 0.0),
   ('(Licencia de inhumación o cremación- Registro de Defunción)', 0.04),
   ('Velación normal (24 horas)', 0.31),
   ('Asesoria las 24 horas', 0.0)]),
 ('PARQUES Y FUNERARIAS — Estilo Superior',
  'parques',
  'estilo superior',
  8,
  [('Recogida del cuerpo dentro del perímetro urbano', 0.04),
   ('Preparación normal del cuerpo', 0.09),
   ('Cofre funebre "Superior" o el equivalente a talla y peso de fallecido', 0.41),
   ('Traslado urbano de la persona fallecida a la sala de velación y Campo Santo', 0.0),
   ('(Carroza Funebre)', 0.03),
   ('Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)', 0.02),
   ('Cafeteria (Bebidas calientes en sala)', 0.05),
   ('Carteles Virtuales', 0.01),
   ('Trámites ante autoridades competentes', 0.0),
   ('(Licencia de inhumación o cremación- Registro de Defunción)', 0.04),
   ('Velación normal (24 horas)', 0.31),
   ('Asesoria las 24 horas', 0.0)]),
 ('PARQUES Y FUNERARIAS — Estilo Excelencia',
  'parques',
  'estilo excelencia',
  8,
  [('Recogida del cuerpo dentro del perímetro urbano', 0.04),
   ('Preparación normal del cuerpo', 0.09),
   ('Cofre funebre "Excelencia" o el equivalente a talla y peso de fallecido', 0.41),
   ('Traslado urbano de la persona fallecida a la sala de velación y Campo Santo', 0.0),
   ('(Carroza Funebre)', 0.03),
   ('Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)', 0.02),
   ('Cafeteria (Bebidas calientes en sala)', 0.05),
   ('Carteles Virtuales', 0.01),
   ('Trámites ante autoridades competentes', 0.0),
   ('(Licencia de inhumación o cremación- Registro de Defunción)', 0.04),
   ('Velación normal (24 horas)', 0.31),
   ('Asesoria las 24 horas', 0.0)]),
 ('PARQUES Y FUNERARIAS — Estilo Extra',
  'parques',
  'estilo extra',
  8,
  [('Recogida del cuerpo dentro del perímetro urbano', 0.04),
   ('Preparación normal del cuerpo', 0.09),
   ('Cofre funebre "Extra" o el equivalente a talla y peso de fallecido', 0.41),
   ('Traslado urbano de la persona fallecida a la sala de velación y Campo Santo', 0.0),
   ('(Carroza Funebre)', 0.03),
   ('Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)', 0.02),
   ('Cafeteria (Bebidas calientes en sala)', 0.05),
   ('Carteles Virtuales', 0.01),
   ('Trámites ante autoridades competentes', 0.0),
   ('(Licencia de inhumación o cremación- Registro de Defunción)', 0.04),
   ('Velación normal (24 horas)', 0.31),
   ('Asesoria las 24 horas', 0.0)])]


def upgrade() -> None:
    op.add_column("certificate_requests", sa.Column("fecha_servicio", sa.Date(), nullable=True))
    for col in _NULLABLE:
        op.alter_column("certificate_requests", col, nullable=True)

    conn = op.get_bind()
    for viejo, nuevo in _TIPOS_RENOMBRADOS:
        conn.execute(
            sa.text("UPDATE certificate_requests SET tipo_certificado = :n WHERE tipo_certificado = :v"),
            {"n": nuevo, "v": viejo},
        )

    for nombre, empresa_key, servicio_key, orden, lineas in _PLANTILLAS:
        existe = conn.execute(
            sa.text("SELECT 1 FROM servicios WHERE empresa_key = :e AND servicio_key = :s"),
            {"e": empresa_key, "s": servicio_key},
        ).first()
        if existe:
            continue
        svc_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO servicios (id, nombre, empresa_key, servicio_key, orden, is_active, created_at, updated_at) "
                "VALUES (:id, :nombre, :e, :s, :orden, true, NOW(), NOW())"
            ),
            {"id": svc_id, "nombre": nombre, "e": empresa_key, "s": servicio_key, "orden": orden},
        )
        for i, (linea, pct) in enumerate(lineas):
            conn.execute(
                sa.text(
                    "INSERT INTO servicio_lineas (id, servicio_id, nombre, porcentaje, orden_linea) "
                    "VALUES (:id, :sid, :n, :p, :o)"
                ),
                {"id": uuid.uuid4(), "sid": svc_id, "n": linea, "p": pct, "o": i},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for nombre, empresa_key, servicio_key, _orden, _lineas in _PLANTILLAS:
        conn.execute(
            sa.text("DELETE FROM servicios WHERE nombre = :n AND empresa_key = :e AND servicio_key = :s"),
            {"n": nombre, "e": empresa_key, "s": servicio_key},
        )
    for viejo, nuevo in _TIPOS_RENOMBRADOS:
        conn.execute(
            sa.text("UPDATE certificate_requests SET tipo_certificado = :v WHERE tipo_certificado = :n"),
            {"n": nuevo, "v": viejo},
        )
    # Las columnas vuelven a NOT NULL solo si no hay filas vacías; si las hay, el downgrade falla a propósito.
    for col in _NULLABLE:
        op.alter_column("certificate_requests", col, nullable=False)
    op.drop_column("certificate_requests", "fecha_servicio")
