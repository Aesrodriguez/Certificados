import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_csrf_token
from app.core.templating import templates
from app.db.session import get_db
from app.dependencies.auth import get_current_session, require_role
from app.dependencies.csrf import verify_csrf
from app.models.session import Session as DbSession
from app.models.user import RoleEnum, User
from app.services import user_service

router = APIRouter(prefix="/admin", dependencies=[Depends(require_role(RoleEnum.ADMIN))])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/users")
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    users = await user_service.list_users(db)
    return templates.TemplateResponse(
        request,
        "admin/users_list.html",
        {
            "current_user": session.user,
            "csrf_token": generate_csrf_token(session.csrf_secret),
            "users": users,
            "roles": list(RoleEnum),
        },
    )


@router.get("/users/new")
async def new_user_form(
    request: Request,
    session: DbSession = Depends(get_current_session),
):
    return templates.TemplateResponse(
        request,
        "admin/user_form.html",
        {
            "current_user": session.user,
            "csrf_token": generate_csrf_token(session.csrf_secret),
            "roles": list(RoleEnum),
            "error": None,
        },
    )


@router.post("/users", dependencies=[Depends(verify_csrf)])
async def create_user(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: RoleEnum = Form(...),
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    if len(password) < 10:
        return templates.TemplateResponse(
            request,
            "admin/user_form.html",
            {
                "current_user": session.user,
                "csrf_token": generate_csrf_token(session.csrf_secret),
                "roles": list(RoleEnum),
                "error": "La contraseña debe tener al menos 10 caracteres.",
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        await user_service.create_user(
            db,
            actor=session.user,
            email=email,
            full_name=full_name,
            password=password,
            role=role,
            ip_address=_ip(request),
        )
    except user_service.UserServiceError as exc:
        return templates.TemplateResponse(
            request,
            "admin/user_form.html",
            {
                "current_user": session.user,
                "csrf_token": generate_csrf_token(session.csrf_secret),
                "roles": list(RoleEnum),
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/role", dependencies=[Depends(verify_csrf)])
async def change_role(
    user_id: uuid.UUID,
    request: Request,
    role: RoleEnum = Form(...),
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    target = await user_service.get_user_or_none(db, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if target.id == session.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio rol.",
        )

    await user_service.set_user_role(
        db, actor=session.user, target=target, new_role=role, ip_address=_ip(request)
    )
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/disable", dependencies=[Depends(verify_csrf)])
async def disable_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    target = await user_service.get_user_or_none(db, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if target.id == session.user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta.",
        )

    await user_service.set_user_active(
        db, actor=session.user, target=target, is_active=False, ip_address=_ip(request)
    )
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/enable", dependencies=[Depends(verify_csrf)])
async def enable_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    target = await user_service.get_user_or_none(db, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await user_service.set_user_active(
        db, actor=session.user, target=target, is_active=True, ip_address=_ip(request)
    )
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)
