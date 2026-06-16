from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    generate_csrf_secret,
    generate_session_token,
    hash_session_token,
    verify_password,
)
from app.models.audit_log import AuditActionEnum
from app.models.session import Session
from app.models.user import User
from app.services.audit_service import log_action

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


class AuthError(Exception):
    """Raised for any login failure. Message is always generic by design —
    never reveals whether the cause was a bad password, unknown email, a
    locked account, or a disabled account, to avoid user enumeration."""


GENERIC_LOGIN_ERROR = "Correo o contraseña incorrectos, o la cuenta está bloqueada temporalmente."


async def authenticate(
    db: AsyncSession, email: str, password: str, ip_address: str | None
) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if user is not None and user.locked_until and user.locked_until > now:
        verify_password(password, None)  # constant-time decoy
        raise AuthError(GENERIC_LOGIN_ERROR)

    password_ok = verify_password(password, user.hashed_password if user else None)

    if user is None or not password_ok or not user.is_active:
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = now + LOCKOUT_DURATION
            await log_action(
                db,
                actor_user_id=user.id,
                action=AuditActionEnum.LOGIN_FAILED,
                entity_type="user",
                entity_id=user.id,
                ip_address=ip_address,
            )
            await db.commit()
        raise AuthError(GENERIC_LOGIN_ERROR)

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    await log_action(
        db,
        actor_user_id=user.id,
        action=AuditActionEnum.LOGIN_SUCCESS,
        entity_type="user",
        entity_id=user.id,
        ip_address=ip_address,
    )
    await db.commit()
    return user


async def create_session(
    db: AsyncSession, user: User, ip_address: str | None, user_agent: str | None
) -> str:
    raw_token = generate_session_token()
    session = Session(
        session_token_hash=hash_session_token(raw_token),
        user_id=user.id,
        csrf_secret=generate_csrf_secret(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.SESSION_LIFETIME_MINUTES),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    await db.commit()
    return raw_token


async def get_valid_session(db: AsyncSession, raw_token: str) -> Session | None:
    token_hash = hash_session_token(raw_token)
    result = await db.execute(
        select(Session)
        .where(Session.session_token_hash == token_hash)
        .options(selectinload(Session.user))
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None
    if session.expires_at < datetime.now(timezone.utc):
        return None
    if session.user is None or not session.user.is_active:
        return None

    session.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    return session


async def revoke_session(db: AsyncSession, raw_token: str) -> None:
    token_hash = hash_session_token(raw_token)
    result = await db.execute(select(Session).where(Session.session_token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is not None:
        await db.delete(session)
        await db.commit()


async def revoke_all_sessions_for_user(db: AsyncSession, user_id) -> None:
    result = await db.execute(select(Session).where(Session.user_id == user_id))
    for session in result.scalars().all():
        await db.delete(session)
    await db.commit()
