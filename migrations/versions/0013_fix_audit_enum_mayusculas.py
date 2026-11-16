"""Corrige valores del enum de auditoría a MAYÚSCULAS

SQLAlchemy guarda los Enum de Python por su NOMBRE (USER_UPDATED), no por su
valor (user_updated). Las migraciones 0005 y 0007 agregaron los valores en
minúsculas, así que editar/eliminar usuarios (p. ej. cambiar contraseña)
fallaba con "invalid input value for enum audit_action_enum: USER_UPDATED".
La 0006 además pasó filas de PASSWORD_RESET_* a minúsculas, que SQLAlchemy no
puede leer de vuelta. Aquí se agregan los nombres en mayúsculas y se
normalizan las filas existentes.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-16
"""
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

_VALORES = {
    "user_updated": "USER_UPDATED",
    "user_deleted": "USER_DELETED",
    "cert_deleted": "CERT_DELETED",
    "password_reset_requested": "PASSWORD_RESET_REQUESTED",
    "password_reset_completed": "PASSWORD_RESET_COMPLETED",
}


def upgrade() -> None:
    # ADD VALUE debe confirmarse antes de poder usar el valor nuevo.
    with op.get_context().autocommit_block():
        for mayus in _VALORES.values():
            op.execute(f"ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS '{mayus}'")

    for minus, mayus in _VALORES.items():
        op.execute(f"UPDATE audit_logs SET action = '{mayus}' WHERE action = '{minus}'")


def downgrade() -> None:
    # PostgreSQL no permite quitar valores de un enum; las filas quedan en mayúsculas,
    # que es como las escribe la aplicación.
    pass
