"""Add user_updated/user_deleted audit actions; audit_logs FK ON DELETE SET NULL

Revision ID: d9e4f5a6b7c8
Revises: c8d3e4f5a6b7
Create Date: 2026-06-17 00:00:00.000000
"""
from alembic import op

revision = "d9e4f5a6b7c8"
down_revision = "c8d3e4f5a6b7"
branch_labels = None
depends_on = None

# Raw SQL to discover the actual FK constraint name in case it differs from
# the generated name.  Alembic's op.f() marks a name as already-formatted,
# but if the DB was bootstrapped via create_all() instead of migration 0001
# the constraint might have a system-generated name.
_DROP_FK_SQL = """
DO $$
DECLARE
    cname text;
BEGIN
    -- Try the expected name first
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_type = 'FOREIGN KEY'
          AND table_name      = 'audit_logs'
          AND constraint_name = 'fk_audit_logs_actor_user_id_users'
    ) THEN
        ALTER TABLE audit_logs DROP CONSTRAINT fk_audit_logs_actor_user_id_users;
        RETURN;
    END IF;
    -- Fall back: find any FK from audit_logs.actor_user_id -> users
    SELECT tc.constraint_name INTO cname
    FROM   information_schema.table_constraints  tc
    JOIN   information_schema.key_column_usage   kcu
           ON kcu.constraint_name = tc.constraint_name
    JOIN   information_schema.referential_constraints rc
           ON rc.constraint_name  = tc.constraint_name
    JOIN   information_schema.table_constraints  tc2
           ON tc2.constraint_name = rc.unique_constraint_name
    WHERE  tc.constraint_type = 'FOREIGN KEY'
      AND  tc.table_name      = 'audit_logs'
      AND  kcu.column_name    = 'actor_user_id'
      AND  tc2.table_name     = 'users'
    LIMIT 1;
    IF cname IS NOT NULL THEN
        EXECUTE 'ALTER TABLE audit_logs DROP CONSTRAINT ' || quote_ident(cname);
    END IF;
END $$;
"""

_ADD_FK_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints tc
        JOIN   information_schema.referential_constraints  rc
               ON rc.constraint_name = tc.constraint_name
        WHERE  tc.constraint_type = 'FOREIGN KEY'
          AND  tc.table_name      = 'audit_logs'
          AND  rc.delete_rule     = 'SET NULL'
    ) THEN
        ALTER TABLE audit_logs
        ADD CONSTRAINT fk_audit_logs_actor_user_id_users
        FOREIGN KEY (actor_user_id) REFERENCES users(id)
        ON DELETE SET NULL;
    END IF;
END $$;
"""


def upgrade() -> None:
    # Extend the audit action enum
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'user_updated'")
    op.execute("ALTER TYPE audit_action_enum ADD VALUE IF NOT EXISTS 'user_deleted'")

    # Change audit_logs.actor_user_id FK to ON DELETE SET NULL so that
    # deleting a user nullifies their audit log actor references instead of blocking.
    # Uses raw SQL with IF EXISTS checks to handle any constraint name variant.
    op.execute(_DROP_FK_SQL)
    op.execute(_ADD_FK_SQL)


def downgrade() -> None:
    op.drop_constraint(
        "fk_audit_logs_actor_user_id_users",
        "audit_logs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_audit_logs_actor_user_id_users",
        "audit_logs",
        "users",
        ["actor_user_id"],
        ["id"],
    )
    # PostgreSQL does not support removing enum values; downgrade skips that step.
