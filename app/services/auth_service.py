from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    generate_csrf_secret,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.models.audit_log import AuditActionEnum
from app.models.password_reset_token import PasswordResetToken
from app.models.session import Session
from app.models.user import User
from app.services.audit_service import log_action

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)
PASSWORD_RESET_LIFETIME_MINUTES = 30


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


async def create_password_reset_token(
    db: AsyncSession, email: str
) -> tuple[str, User] | None:
    """Creates a reset token for the given email. Returns (raw_token, user) if the
    email belongs to an active account, None otherwise. The caller should always
    show the same success message regardless of the return value."""
    result = await db.execute(
        select(User).where(User.email == email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None

    # Invalidate any prior unused tokens for this user
    existing = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at == None,
        )
    )
    for old_token in existing.scalars().all():
        old_token.used_at = datetime.now(timezone.utc)

    raw_token = generate_session_token()
    reset_token = PasswordResetToken(
        token_hash=hash_session_token(raw_token),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_LIFETIME_MINUTES),
    )
    db.add(reset_token)
    await db.commit()
    return raw_token, user


async def consume_password_reset_token(
    db: AsyncSession, raw_token: str, new_password: str
) -> User | None:
    """Verifies the token, updates the password, and revokes all sessions.
    Returns the user on success, None if the token is invalid or expired."""
    token_hash = hash_session_token(raw_token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at == None,
            PasswordResetToken.expires_at > now,
        )
        .options(selectinload(PasswordResetToken.user))
    )
    reset_token = result.scalar_one_or_none()
    if reset_token is None or not reset_token.user.is_active:
        return None

    reset_token.used_at = now
    reset_token.user.hashed_password = hash_password(new_password)
    reset_token.user.failed_login_attempts = 0
    reset_token.user.locked_until = None
    await db.commit()

    await revoke_all_sessions_for_user(db, reset_token.user.id)
    return reset_token.user
