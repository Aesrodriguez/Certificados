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
from app.services.email_service import EmailDeliveryError, send_password_reset_email

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


@router.get("/forgot-password")
async def forgot_password_form(request: Request):
    return templates.TemplateResponse(request, "auth/forgot_password.html", {"sent": False})


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password_submit(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    ip_address = request.client.host if request.client else None
    result = await auth_service.create_password_reset_token(db, email)
    if result is not None:
        raw_token, user = result
        reset_url = str(request.base_url).rstrip("/") + f"/reset-password?token={raw_token}"
        try:
            send_password_reset_email(user.email, user.full_name, reset_url)
        except EmailDeliveryError:
            pass  # silent — never reveal if the email exists
        await log_action(
            db,
            actor_user_id=user.id,
            action=AuditActionEnum.PASSWORD_RESET_REQUESTED,
            entity_type="user",
            entity_id=user.id,
            ip_address=ip_address,
        )
        await db.commit()
    # Always show the same message (prevents user enumeration)
    return templates.TemplateResponse(
        request, "auth/forgot_password.html", {"sent": True}
    )


@router.get("/reset-password")
async def reset_password_form(request: Request, token: str = ""):
    return templates.TemplateResponse(
        request, "auth/reset_password.html", {"token": token, "error": None}
    )


@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    ip_address = request.client.host if request.client else None
    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {"token": token, "error": "Las contraseñas no coinciden."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {"token": token, "error": "La contraseña debe tener al menos 8 caracteres."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user = await auth_service.consume_password_reset_token(db, token, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {"token": token, "error": "El enlace es inválido o ha expirado. Solicita uno nuevo."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    await log_action(
        db,
        actor_user_id=user.id,
        action=AuditActionEnum.PASSWORD_RESET_COMPLETED,
        entity_type="user",
        entity_id=user.id,
        ip_address=ip_address,
    )
    await db.commit()
    return RedirectResponse(
        url="/login?msg=Contraseña restablecida correctamente. Inicia sesión.",
        status_code=status.HTTP_303_SEE_OTHER,
    )


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
