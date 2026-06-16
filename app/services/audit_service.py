import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditActionEnum, AuditLog


async def log_action(
    db: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: AuditActionEnum,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Record an audit entry in the *same* db session/transaction as the
    caller's state change, so the two can never silently diverge — the
    caller is responsible for committing."""
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            metadata_json=metadata,
        )
    )
