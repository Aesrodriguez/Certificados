from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.templating import templates
from app.db.session import get_db
from app.dependencies.auth import get_current_session
from app.dependencies.csrf import verify_csrf
from app.models.audit_log import AuditActionEnum
from app.models.session import Session as DbSession
from app.services import auth_service
from app.services.audit_service import log_action

router = APIRouter()


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {"error": None})


@router.post("/login")
@limiter.limit("10/minute")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    ip_address = request.client.host if request.client else None
    try:
        user = await auth_service.authenticate(db, email, password, ip_address)
    except auth_service.AuthError as exc:
        return templates.TemplateResponse(
            request, "auth/login.html", {"error": str(exc)}, status_code=status.HTTP_401_UNAUTHORIZED
        )

    raw_token = await auth_service.create_session(
        db, user, ip_address=ip_address, user_agent=request.headers.get("user-agent")
    )

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        max_age=settings.SESSION_LIFETIME_MINUTES * 60,
        path="/",
    )
    return response


@router.post("/logout", dependencies=[Depends(verify_csrf)])
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    await log_action(
        db,
        actor_user_id=session.user_id,
        action=AuditActionEnum.LOGOUT,
        entity_type="user",
        entity_id=session.user_id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if token:
        await auth_service.revoke_session(db, token)

    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return response
