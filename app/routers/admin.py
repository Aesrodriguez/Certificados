import io
import logging
import uuid
from datetime import date
from urllib.parse import urlencode

import xlrd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.core.security import generate_csrf_token
from app.core.templating import templates
from app.db.session import get_db
from app.dependencies.auth import get_current_session, require_role
from app.dependencies.csrf import verify_csrf
from app.models.audit_log import AuditActionEnum
from app.models.certificate_request import CertificateRequest
from app.models.session import Session as DbSession
from app.models.user import RoleEnum
from app.services import appsetting_service, certificate_service, marca_service, user_service
from app.services.audit_service import log_action
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", dependencies=[Depends(require_role(RoleEnum.ADMIN))])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _ctx(session: DbSession, **extra) -> dict:
    return {
        "current_user": session.user,
        "csrf_token": generate_csrf_token(session.csrf_secret),
        "roles": list(RoleEnum),
        **extra,
    }


@router.get("/users")
async def list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
    msg: str | None = Query(None),
    error: str | None = Query(None),
):
    users = await user_service.list_users(db)
    return templates.TemplateResponse(
        request, "admin/users_list.html",
        _ctx(session, users=users, msg=msg, error=error),
    )


@router.get("/users/new")
async def new_user_form(
    request: Request,
    session: DbSession = Depends(get_current_session),
):
    return templates.TemplateResponse(
        request, "admin/user_form.html",
        _ctx(session, user_obj=None, error=None),
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
            request, "admin/user_form.html",
            _ctx(session, user_obj=None, error="La contraseña debe tener al menos 10 caracteres."),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        await user_service.create_user(
            db, actor=session.user, email=email, full_name=full_name,
            password=password, role=role, ip_address=_ip(request),
        )
    except user_service.UserServiceError as exc:
        return templates.TemplateResponse(
            request, "admin/user_form.html",
            _ctx(session, user_obj=None, error=str(exc)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(url="/admin/users?msg=Usuario+creado", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/users/{user_id}/edit")
async def edit_user_form(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    target = await user_service.get_user_or_none(db, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return templates.TemplateResponse(
        request, "admin/user_form.html",
        _ctx(session, user_obj=target, error=None),
    )


@router.post("/users/{user_id}/edit", dependencies=[Depends(verify_csrf)])
async def update_user(
    user_id: uuid.UUID,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    role: RoleEnum = Form(...),
    password: str = Form(""),
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    target = await user_service.get_user_or_none(db, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if target.id == session.user.id and role != target.role:
        return templates.TemplateResponse(
            request, "admin/user_form.html",
            _ctx(session, user_obj=target, error="No puedes cambiar tu propio rol."),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    new_password = password.strip() if password.strip() else None
    if new_password and len(new_password) < 10:
        return templates.TemplateResponse(
            request, "admin/user_form.html",
            _ctx(session, user_obj=target, error="La contraseña debe tener al menos 10 caracteres."),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        await user_service.update_user(
            db, actor=session.user, target=target,
            full_name=full_name, email=email, role=role,
            password=new_password, ip_address=_ip(request),
        )
    except user_service.UserServiceError as exc:
        return templates.TemplateResponse(
            request, "admin/user_form.html",
            _ctx(session, user_obj=target, error=str(exc)),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(url="/admin/users?msg=Usuario+actualizado", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/delete", dependencies=[Depends(verify_csrf)])
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    target = await user_service.get_user_or_none(db, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if target.id == session.user.id:
        return RedirectResponse(
            url="/admin/users?error=No+puedes+eliminar+tu+propia+cuenta.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        await user_service.delete_user(
            db, actor=session.user, target=target, ip_address=_ip(request)
        )
    except user_service.UserServiceError as exc:
        from urllib.parse import quote
        return RedirectResponse(
            url=f"/admin/users?error={quote(str(exc))}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url="/admin/users?msg=Usuario+eliminado", status_code=status.HTTP_303_SEE_OTHER)


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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes cambiar tu propio rol.")
    await user_service.set_user_role(db, actor=session.user, target=target, new_role=role, ip_address=_ip(request))
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No puedes desactivar tu propia cuenta.")
    await user_service.set_user_active(db, actor=session.user, target=target, is_active=False, ip_address=_ip(request))
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
    await user_service.set_user_active(db, actor=session.user, target=target, is_active=True, ip_address=_ip(request))
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


# ── Configuración ─────────────────────────────────────────────────────────────

@router.get("/configuracion")
async def configuracion_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
    msg: str | None = Query(None),
    error: str | None = Query(None),
):
    email_enabled = await appsetting_service.get_setting(db, "email_enabled", default="false")
    required_fields = await appsetting_service.get_required_fields(db)
    return templates.TemplateResponse(
        request, "admin/configuracion.html",
        _ctx(
            session,
            email_enabled=(email_enabled == "true"),
            required_fields=required_fields,
            configurable_fields=appsetting_service.CONFIGURABLE_FIELDS,
            msg=msg,
            error=error,
            ranuras=marca_service.RANURAS,
            imagenes=await marca_service.guardadas(db),
            imagen_urls=await marca_service.urls(db),
            proximo_consecutivo=await certificate_service.proximo_consecutivo(db),
            anio_actual=date.today().year,
        ),
    )


@router.post("/configuracion", dependencies=[Depends(verify_csrf)])
async def configuracion_save(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    form = await request.form()
    email_enabled = "true" if form.get("email_enabled") == "1" else "false"
    await appsetting_service.set_setting(db, "email_enabled", email_enabled)
    req_fields = list(form.getlist("req_field"))
    await appsetting_service.set_required_fields(db, req_fields)
    return RedirectResponse(url="/admin/configuracion?msg=Configuración+guardada.", status_code=303)


@router.post("/configuracion/imagen/{clave}", dependencies=[Depends(verify_csrf)])
async def configuracion_imagen(
    clave: str,
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    r = marca_service.ranura(clave)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    datos = await archivo.read(marca_service.MAX_BYTES + 1)
    try:
        await marca_service.guardar(db, clave, datos, archivo.filename or "")
    except marca_service.ImagenInvalida as exc:
        return RedirectResponse(
            url=f"/admin/configuracion?{urlencode({'error': f'{r.titulo}: {exc}'})}#imagenes",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/admin/configuracion?{urlencode({'msg': f'{r.titulo} actualizado.'})}#imagenes",
        status_code=303,
    )


@router.post("/configuracion/imagen/{clave}/restablecer", dependencies=[Depends(verify_csrf)])
async def configuracion_imagen_restablecer(clave: str, db: AsyncSession = Depends(get_db)):
    r = marca_service.ranura(clave)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await marca_service.restablecer(db, clave)
    return RedirectResponse(
        url=f"/admin/configuracion?{urlencode({'msg': f'{r.titulo}: se restableció la imagen original.'})}#imagenes",
        status_code=303,
    )


# ── Importar Excel ─────────────────────────────────────────────────────────────

def _parse_xls_date(cell, datemode: int) -> date | None:
    if cell.ctype == xlrd.XL_CELL_DATE:
        try:
            tup = xlrd.xldate_as_tuple(cell.value, datemode)
            return date(tup[0], tup[1], tup[2])
        except Exception:
            return None
    return None


def _str_cell(cell) -> str:
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        v = cell.value
        return str(int(v)) if v == int(v) else str(v)
    return str(cell.value).strip()


@router.get("/importar")
async def importar_page(
    request: Request,
    session: DbSession = Depends(get_current_session),
):
    return templates.TemplateResponse(
        request, "admin/importar.html",
        _ctx(session, results=None),
    )


@router.post("/importar", dependencies=[Depends(verify_csrf)])
async def importar_submit(
    request: Request,
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    raw = await archivo.read(MAX_SIZE + 1)
    if len(raw) > MAX_SIZE:
        return templates.TemplateResponse(
            request, "admin/importar.html",
            _ctx(session, results=None, error="El archivo supera el límite de 10 MB."),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        wb = xlrd.open_workbook(file_contents=raw)
    except Exception:
        return templates.TemplateResponse(
            request, "admin/importar.html",
            _ctx(session, results=None, error="No se pudo leer el archivo. Asegúrate de subir un .xls válido."),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        sh = wb.sheet_by_name("BASE")
    except xlrd.biffh.XLRDError:
        try:
            sh = wb.sheets()[0]
        except Exception:
            return templates.TemplateResponse(
                request, "admin/importar.html",
                _ctx(session, results=None, error="No se encontró la hoja 'BASE' en el archivo."),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    datemode = wb.datemode
    deleted, updated, not_found, errors = [], [], [], []

    for row_idx in range(1, sh.nrows):
        row = sh.row(row_idx)
        if len(row) < 18:
            continue

        cedula_fall = _str_cell(row[11]).strip()
        estado = _str_cell(row[17]).strip().upper()

        if not cedula_fall:
            continue

        result = await db.execute(
            select(CertificateRequest).where(
                CertificateRequest.fallecido_numero_documento == cedula_fall
            )
        )
        cert = result.scalar_one_or_none()

        if cert is None:
            not_found.append(cedula_fall)
            continue

        try:
            if estado == "ENVIADO AL CLIENTE":
                cert_id = cert.id
                cert_nombre = cert.fallecido_nombre_completo
                await db.delete(cert)
                await db.flush()
                await log_action(
                    db,
                    actor_user_id=session.user_id,
                    action=AuditActionEnum.CERT_DELETED,
                    entity_type="certificate_request",
                    entity_id=cert_id,
                    ip_address=_ip(request),
                    metadata={"reason": "importacion_excel", "fallecido": cert_nombre},
                )
                deleted.append(cedula_fall)
            elif estado == "SOLICITADO":
                empresa = _str_cell(row[3])
                if empresa:
                    cert.empresa = empresa[:100]
                email = _str_cell(row[4])
                if email:
                    cert.cliente_email = email[:255]
                solicitante = _str_cell(row[5])
                if solicitante:
                    cert.cliente_nombre_completo = solicitante[:255]
                cedula_cli = _str_cell(row[6])
                if cedula_cli:
                    cert.cliente_numero_documento = cedula_cli[:30]
                doc_sol = _str_cell(row[7])
                if doc_sol:
                    cert.tipo_certificado = doc_sol[:100]
                num_aviso = _str_cell(row[8])
                if num_aviso:
                    cert.numero_aviso = num_aviso[:50]
                fecha_svc = _parse_xls_date(row[9], datemode)
                if fecha_svc:
                    cert.fallecido_fecha_fallecimiento = fecha_svc
                nombre_fall = _str_cell(row[10])
                if nombre_fall:
                    cert.fallecido_nombre_completo = nombre_fall[:255]
                fecha_afil = _parse_xls_date(row[12], datemode)
                if fecha_afil:
                    cert.fecha_afiliacion = fecha_afil
                recibo = _str_cell(row[14])
                if recibo:
                    cert.numero_recibo_caja = recibo[:50]
                contrato = _str_cell(row[15])
                if contrato:
                    cert.numero_contrato = contrato[:100]
                obs = _str_cell(row[16])
                if obs:
                    cert.observaciones = obs[:2000]
                await log_action(
                    db,
                    actor_user_id=session.user_id,
                    action=AuditActionEnum.CERT_UPDATED,
                    entity_type="certificate_request",
                    entity_id=cert.id,
                    ip_address=_ip(request),
                    metadata={"reason": "importacion_excel"},
                )
                updated.append(cedula_fall)
        except Exception as exc:
            logger.error("Excel import error row %d: %s", row_idx, type(exc).__name__)
            errors.append(cedula_fall)

    await db.commit()

    results = {
        "deleted": deleted,
        "updated": updated,
        "not_found": not_found,
        "errors": errors,
    }
    return templates.TemplateResponse(
        request, "admin/importar.html",
        _ctx(session, results=results),
    )
