import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.audit_log import AuditActionEnum
from app.models.certificate_request import CertificateRequest
from app.models.user import RoleEnum, User
from app.services.audit_service import log_action
from app.services.auth_service import revoke_all_sessions_for_user


class UserServiceError(Exception):
    """Raised for user-management failures meant to be shown to the admin."""


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def create_user(
    db: AsyncSession,
    *,
    actor: User,
    email: str,
    full_name: str,
    password: str,
    role: RoleEnum,
    ip_address: str | None,
) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise UserServiceError(f"Ya existe un usuario con el correo {email}.")

    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await log_action(
        db,
        actor_user_id=actor.id,
        action=AuditActionEnum.USER_CREATED,
        entity_type="user",
        entity_id=user.id,
        ip_address=ip_address,
        metadata=({"role": role.value}),
    )
    await db.commit()
    return user


async def update_user(
    db: AsyncSession,
    *,
    actor: User,
    target: User,
    full_name: str,
    email: str,
    role: RoleEnum,
    password: str | None,
    ip_address: str | None,
) -> None:
    if email != target.email:
        conflict = await db.execute(
            select(User).where(User.email == email, User.id != target.id)
        )
        if conflict.scalar_one_or_none() is not None:
            raise UserServiceError(f"Ya existe otro usuario con el correo {email}.")

    changes: dict = {}
    if target.full_name != full_name:
        changes["full_name"] = {"old": target.full_name, "new": full_name}
        target.full_name = full_name
    if target.email != email:
        changes["email"] = {"old": target.email, "new": email}
        target.email = email
    if target.role != role:
        changes["role"] = {"old": target.role.value, "new": role.value}
        target.role = role
    if password:
        target.hashed_password = hash_password(password)
        changes["password"] = "changed"

    await log_action(
        db,
        actor_user_id=actor.id,
        action=AuditActionEnum.USER_UPDATED,
        entity_type="user",
        entity_id=target.id,
        ip_address=ip_address,
        metadata=changes,
    )
    await db.commit()


async def delete_user(
    db: AsyncSession,
    *,
    actor: User,
    target: User,
    ip_address: str | None,
) -> None:
    count_result = await db.execute(
        select(func.count()).where(
            or_(
                CertificateRequest.asesor_id == target.id,
                CertificateRequest.revisor_id == target.id,
            )
        )
    )
    cert_count = count_result.scalar_one()
    if cert_count > 0:
        raise UserServiceError(
            f"No se puede eliminar: el usuario tiene {cert_count} solicitud(es) "
            "de certificado asociadas. Desactívalo en cambio."
        )

    await revoke_all_sessions_for_user(db, target.id)

    await log_action(
        db,
        actor_user_id=actor.id,
        action=AuditActionEnum.USER_DELETED,
        entity_type="user",
        entity_id=target.id,
        ip_address=ip_address,
        metadata={"email": target.email, "role": target.role.value},
    )
    await db.flush()
    await db.delete(target)
    await db.commit()


async def set_user_role(
    db: AsyncSession, *, actor: User, target: User, new_role: RoleEnum, ip_address: str | None
) -> None:
    old_role = target.role
    target.role = new_role
    await log_action(
        db,
        actor_user_id=actor.id,
        action=AuditActionEnum.USER_ROLE_CHANGED,
        entity_type="user",
        entity_id=target.id,
        ip_address=ip_address,
        metadata={"old_role": old_role.value, "new_role": new_role.value},
    )
    await db.commit()


async def set_user_active(
    db: AsyncSession, *, actor: User, target: User, is_active: bool, ip_address: str | None
) -> None:
    target.is_active = is_active
    action = AuditActionEnum.USER_ENABLED if is_active else AuditActionEnum.USER_DISABLED
    await log_action(
        db,
        actor_user_id=actor.id,
        action=action,
        entity_type="user",
        entity_id=target.id,
        ip_address=ip_address,
    )
    await db.commit()

    if not is_active:
        await revoke_all_sessions_for_user(db, target.id)


async def get_user_or_none(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
