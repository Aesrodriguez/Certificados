from fastapi import Depends, Form, HTTPException, status

from app.core.security import verify_csrf_token
from app.dependencies.auth import get_current_session
from app.models.session import Session as DbSession


async def verify_csrf(
    csrf_token: str = Form(...),
    session: DbSession = Depends(get_current_session),
) -> None:
    if not verify_csrf_token(session.csrf_secret, csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token inválido")
