from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.session import Session as DbSession
from app.models.user import RoleEnum, User
from app.services import auth_service


class RedirectToLogin(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})


async def get_current_session(
    request: Request, db: AsyncSession = Depends(get_db)
) -> DbSession:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise RedirectToLogin()
    session = await auth_service.get_valid_session(db, token)
    if session is None:
        raise RedirectToLogin()
    request.state.session = session
    return session


async def get_current_user(
    session: DbSession = Depends(get_current_session),
) -> User:
    return session.user


def require_role(*roles: RoleEnum):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
        return user

    return checker
