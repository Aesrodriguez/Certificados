import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_csrf_token
from app.core.templating import templates
from app.db.session import get_db
from app.dependencies.auth import get_current_session, require_role
from app.dependencies.csrf import verify_csrf
from app.models.session import Session as DbSession
from app.models.user import RoleEnum
from app.services import servicio_service

router = APIRouter(
    prefix="/admin/servicios",
    dependencies=[Depends(require_role(RoleEnum.ADMIN))],
)


def _ctx(session: DbSession, **extra) -> dict:
    return {
        "current_user": session.user,
        "csrf_token": generate_csrf_token(session.csrf_secret),
        **extra,
    }


def _parse_lineas(form) -> list[tuple[str, float]]:
    nombres = form.getlist("linea_nombre")
    pcts = form.getlist("linea_pct")
    lineas = []
    for nom, pct_str in zip(nombres, pcts):
        nom = nom.strip()
        if not nom:
            continue
        try:
            pct = float(pct_str) / 100.0
        except (ValueError, TypeError):
            pct = 0.0
        lineas.append((nom, pct))
    return lineas


@router.get("")
async def list_servicios_view(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
    msg: str | None = Query(None),
    error: str | None = Query(None),
):
    servicios = await servicio_service.list_servicios(db)
    return templates.TemplateResponse(
        request, "admin/servicios/list.html",
        _ctx(session, servicios=servicios, msg=msg, error=error),
    )


@router.get("/new")
async def new_servicio_form(
    request: Request,
    session: DbSession = Depends(get_current_session),
):
    return templates.TemplateResponse(
        request, "admin/servicios/form.html",
        _ctx(session, svc=None, error=None),
    )


@router.post("", dependencies=[Depends(verify_csrf)])
async def create_servicio_post(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    empresa_key = str(form.get("empresa_key", "")).strip().lower()
    servicio_key = str(form.get("servicio_key", "")).strip().lower()
    orden = int(form.get("orden") or 0)
    is_active = form.get("is_active") == "1"
    lineas = _parse_lineas(form)

    if not nombre:
        return templates.TemplateResponse(
            request, "admin/servicios/form.html",
            _ctx(session, svc=None, error="El nombre es requerido."),
            status_code=422,
        )

    await servicio_service.create_servicio(
        db,
        nombre=nombre,
        empresa_key=empresa_key,
        servicio_key=servicio_key,
        orden=orden,
        is_active=is_active,
        lineas=lineas,
    )
    return RedirectResponse(url="/admin/servicios?msg=Servicio+creado+correctamente.", status_code=303)


@router.get("/{servicio_id}")
async def detail_servicio(
    servicio_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
    msg: str | None = Query(None),
):
    svc = await servicio_service.get_servicio(db, servicio_id)
    if svc is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "admin/servicios/detail.html",
        _ctx(session, svc=svc, msg=msg),
    )


@router.get("/{servicio_id}/edit")
async def edit_servicio_form(
    servicio_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    svc = await servicio_service.get_servicio(db, servicio_id)
    if svc is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request, "admin/servicios/form.html",
        _ctx(session, svc=svc, error=None),
    )


@router.post("/{servicio_id}", dependencies=[Depends(verify_csrf)])
async def update_servicio_post(
    servicio_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    svc = await servicio_service.get_servicio(db, servicio_id)
    if svc is None:
        raise HTTPException(status_code=404)

    form = await request.form()
    nombre = str(form.get("nombre", "")).strip()
    empresa_key = str(form.get("empresa_key", "")).strip().lower()
    servicio_key = str(form.get("servicio_key", "")).strip().lower()
    orden = int(form.get("orden") or 0)
    is_active = form.get("is_active") == "1"
    lineas = _parse_lineas(form)

    if not nombre:
        return templates.TemplateResponse(
            request, "admin/servicios/form.html",
            _ctx(session, svc=svc, error="El nombre es requerido."),
            status_code=422,
        )

    await servicio_service.update_servicio(
        db, svc,
        nombre=nombre,
        empresa_key=empresa_key,
        servicio_key=servicio_key,
        orden=orden,
        is_active=is_active,
        lineas=lineas,
    )
    return RedirectResponse(
        url=f"/admin/servicios/{servicio_id}?msg=Servicio+actualizado+correctamente.",
        status_code=303,
    )


@router.post("/{servicio_id}/delete", dependencies=[Depends(verify_csrf)])
async def delete_servicio_post(
    servicio_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    svc = await servicio_service.get_servicio(db, servicio_id)
    if svc is None:
        raise HTTPException(status_code=404)
    await servicio_service.delete_servicio(db, svc)
    return RedirectResponse(url="/admin/servicios?msg=Servicio+eliminado+correctamente.", status_code=303)
