import re
import uuid
from datetime import date

import pydantic
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_csrf_token
from app.core.templating import templates
from app.db.session import get_db
from app.dependencies.auth import get_current_session, require_role
from app.dependencies.csrf import verify_csrf
from app.models.audit_log import AuditActionEnum
from app.models.certificate_request import StatusEnum
from app.models.session import Session as DbSession
from app.models.user import RoleEnum
from app.schemas.certificate_request import CertificateRequestIn
from app.services import appsetting_service, certificate_service, pdf_service, servicio_service
from app.services.audit_service import log_action
from app.services.pdf_service import _numero_a_palabras, _MESES, encrypt_pdf

router = APIRouter(
    prefix="/certificates",
    dependencies=[Depends(require_role(RoleEnum.ADMIN, RoleEnum.ASESOR, RoleEnum.REVISOR))],
)


def _parse_servicios(form) -> list | None:
    nombres = form.getlist("svc_nombre")
    valores = form.getlist("svc_valor")
    lineas = []
    for nom, val_str in zip(nombres, valores):
        nom = nom.strip()
        if not nom:
            continue
        try:
            val = int(val_str or 0)
        except (ValueError, TypeError):
            val = 0
        lineas.append({"nombre": nom, "valor": val})
    return lineas or None


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _signer(cert) -> tuple[str, str]:
    """Return (nombre, cargo) for the certificate signature block.

    Priority: FIRMA_NOMBRE setting → asesor full_name → fallback label.
    """
    nombre = (
        settings.FIRMA_NOMBRE.strip()
        or (cert.asesor.full_name if cert.asesor else "")
        or "Administrador de Ciudad"
    )
    cargo = settings.FIRMA_CARGO.strip() or "Administrador de Ciudad"
    return nombre, cargo


def _ctx(session: DbSession, **extra) -> dict:
    return {
        "current_user": session.user,
        "csrf_token": generate_csrf_token(session.csrf_secret),
        **extra,
    }


PER_PAGE = 25


@router.get("")
async def list_certificates(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
):
    certs, total = await certificate_service.list_for_user(
        db, session.user, status_filter=status_filter, search=q or None, page=page, per_page=PER_PAGE
    )
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    return templates.TemplateResponse(
        request, "certificates/list.html",
        _ctx(
            session,
            certs=certs,
            status_filter=status_filter,
            search=q or "",
            page=page,
            total=total,
            total_pages=total_pages,
            per_page=PER_PAGE,
        ),
    )


@router.get("/new", dependencies=[Depends(require_role(RoleEnum.ASESOR, RoleEnum.ADMIN))])
async def new_certificate_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    required_fields = await appsetting_service.get_required_fields(db)
    return templates.TemplateResponse(
        request,
        "certificates/form.html",
        _ctx(session, cert=None, cert_servicios=[], field_errors={},
             required_fields=required_fields, form_action="/certificates"),
    )


@router.post("", dependencies=[Depends(require_role(RoleEnum.ASESOR, RoleEnum.ADMIN)), Depends(verify_csrf)])
async def create_certificate(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    form = await request.form()
    form_dict = dict(form)
    form_dict["servicios_json"] = _parse_servicios(form)

    required_fields = await appsetting_service.get_required_fields(db)
    all_errors: dict[str, str] = _check_required(form_dict, required_fields)
    data = None
    try:
        data = CertificateRequestIn.model_validate(form_dict)
    except pydantic.ValidationError as exc:
        all_errors.update(_field_errors(exc))

    if all_errors or data is None:
        return templates.TemplateResponse(
            request,
            "certificates/form.html",
            _ctx(
                session,
                cert=form_dict,
                cert_servicios=form_dict.get("servicios_json") or [],
                field_errors=all_errors,
                required_fields=required_fields,
                form_action="/certificates",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    cert = await certificate_service.create_draft(
        db, asesor=session.user, data=data, ip_address=_ip(request)
    )
    return RedirectResponse(url=f"/certificates/{cert.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{cert_id}/quick")
async def certificate_quick_view(
    cert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    """Returns minimal cert data as JSON for the quick-view modal."""
    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        certificate_service.assert_can_view(cert, session.user)
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from fastapi.responses import JSONResponse
    from datetime import date as _date

    def _d(val) -> str | None:
        if val is None:
            return None
        if isinstance(val, _date):
            return val.strftime("%d/%m/%Y")
        return str(val)

    user = session.user
    _editable = cert.status in certificate_service.EDITABLE_STATUSES
    can_edit = (
        user.role == RoleEnum.ADMIN
        or (user.role == RoleEnum.ASESOR and cert.asesor_id == user.id)
    ) and _editable
    can_delete = (
        user.role == RoleEnum.ADMIN
        or (user.role == RoleEnum.ASESOR and cert.asesor_id == user.id and _editable)
    )

    return JSONResponse({
        "id":        str(cert.id),
        "fallecido": cert.fallecido_nombre_completo or "",
        "fdoc":      cert.fallecido_numero_documento or "",
        "ffecha":    _d(cert.fallecido_fecha_fallecimiento) or "—",
        "cliente":   cert.cliente_nombre_completo or "",
        "cdoc":      cert.cliente_numero_documento or "",
        "cemail":    cert.cliente_email or "",
        "tipo":      cert.tipo_certificado or "—",
        "empresa":   cert.empresa or "—",
        "contrato":  cert.numero_contrato or "—",
        "recibo":    cert.numero_recibo_caja or "—",
        "aviso":     cert.numero_aviso or "—",
        "afiliacion": _d(cert.fecha_afiliacion) or "—",
        "obs":       cert.observaciones or "",
        "status":    cert.status.value,
        "fecha":     _d(cert.created_at),
        "can_edit":   can_edit,
        "can_delete": can_delete,
    })


@router.get("/{cert_id}")
async def certificate_detail(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        certificate_service.assert_can_view(cert, session.user)
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    is_admin = session.user.role == RoleEnum.ADMIN
    can_edit = (is_admin or cert.asesor_id == session.user.id) and cert.status in certificate_service.EDITABLE_STATUSES
    can_review = session.user.role in (RoleEnum.REVISOR, RoleEnum.ADMIN) and cert.status.value == "pending"
    return templates.TemplateResponse(
        request,
        "certificates/detail.html",
        _ctx(session, cert=cert, can_edit=can_edit, can_review=can_review),
    )


@router.get("/{cert_id}/edit", dependencies=[Depends(require_role(RoleEnum.ASESOR, RoleEnum.ADMIN))])
async def edit_certificate_form(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        certificate_service.assert_can_edit(cert, session.user)
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    required_fields = await appsetting_service.get_required_fields(db)
    return templates.TemplateResponse(
        request,
        "certificates/form.html",
        _ctx(session, cert=cert, cert_servicios=cert.servicios_json or [], field_errors={},
             required_fields=required_fields, form_action=f"/certificates/{cert.id}"),
    )


@router.post(
    "/{cert_id}", dependencies=[Depends(require_role(RoleEnum.ASESOR, RoleEnum.ADMIN)), Depends(verify_csrf)]
)
async def update_certificate(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    form = await request.form()
    form_dict = dict(form)
    form_dict["servicios_json"] = _parse_servicios(form)

    required_fields = await appsetting_service.get_required_fields(db)
    all_errors: dict[str, str] = _check_required(form_dict, required_fields)
    data = None
    try:
        data = CertificateRequestIn.model_validate(form_dict)
    except pydantic.ValidationError as exc:
        all_errors.update(_field_errors(exc))

    if all_errors or data is None:
        return templates.TemplateResponse(
            request,
            "certificates/form.html",
            _ctx(
                session,
                cert=form_dict,
                cert_servicios=form_dict.get("servicios_json") or [],
                field_errors=all_errors,
                required_fields=required_fields,
                form_action=f"/certificates/{cert_id}",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        await certificate_service.update_draft(
            db, cert=cert, asesor=session.user, data=data, ip_address=_ip(request)
        )
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return RedirectResponse(url=f"/certificates/{cert.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/{cert_id}/delete",
    dependencies=[Depends(verify_csrf)],
)
async def delete_certificate(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    from urllib.parse import quote

    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await certificate_service.delete_cert(
            db, cert=cert, actor=session.user, ip_address=_ip(request)
        )
    except certificate_service.CertificateServiceError as exc:
        return RedirectResponse(
            url=f"/certificates?msg={quote(str(exc))}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Error eliminando solicitud %s", cert_id)
        return RedirectResponse(
            url=f"/certificates?msg={quote('Error al eliminar la solicitud. Intente de nuevo.')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url="/certificates?msg=Solicitud+eliminada+correctamente.",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{cert_id}/submit",
    dependencies=[Depends(require_role(RoleEnum.ASESOR, RoleEnum.ADMIN)), Depends(verify_csrf)],
)
async def submit_certificate(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await certificate_service.submit(
            db, cert=cert, asesor=session.user, ip_address=_ip(request)
        )
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return RedirectResponse(url=f"/certificates/{cert.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/{cert_id}/approve",
    dependencies=[Depends(require_role(RoleEnum.REVISOR, RoleEnum.ADMIN)), Depends(verify_csrf)],
)
async def approve_certificate(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        email_sent = await certificate_service.approve(
            db, cert=cert, revisor=session.user, ip_address=_ip(request)
        )
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    url = f"/certificates/{cert.id}"
    if not email_sent:
        url += "?msg=Aprobado%2C+pero+el+env%C3%ADo+del+correo+fall%C3%B3.+Reint%C3%A9ntalo+desde+el+detalle."
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/{cert_id}/reject",
    dependencies=[Depends(require_role(RoleEnum.REVISOR, RoleEnum.ADMIN)), Depends(verify_csrf)],
)
async def reject_certificate(
    cert_id: uuid.UUID,
    request: Request,
    rejection_comment: str = Form(...),
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await certificate_service.reject(
            db,
            cert=cert,
            revisor=session.user,
            comment=rejection_comment,
            ip_address=_ip(request),
        )
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(url=f"/certificates/{cert.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{cert_id}/preview")
async def preview_certificate(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    # Eager-load asesor to avoid lazy-load blocking the async event loop
    cert = await certificate_service.get_with_asesor(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        certificate_service.assert_can_view(cert, session.user)
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    is_admin = session.user.role == RoleEnum.ADMIN
    can_edit = (is_admin or cert.asesor_id == session.user.id) and cert.status in certificate_service.EDITABLE_STATUSES
    can_review = session.user.role in (RoleEnum.REVISOR, RoleEnum.ADMIN) and cert.status.value == "pending"

    issue_date_obj = cert.reviewed_at.date() if cert.reviewed_at else date.today()
    entry_date = cert.created_at.strftime("%d/%m/%Y") if cert.created_at else issue_date_obj.strftime("%d/%m/%Y")
    total_palabras = _numero_a_palabras(cert.valor_total) if cert.valor_total else ""
    lineas_servicio = (
        await servicio_service.get_lineas_for_cert(
            db, cert.empresa, cert.nombre_servicio, cert.valor_total,
            servicios_json=cert.servicios_json,
        )
        if cert.valor_total
        else []
    )

    fallecimiento_obj = cert.fallecido_fecha_fallecimiento
    if fallecimiento_obj:
        issue_fallecimiento = f"{fallecimiento_obj.day} de {_MESES[fallecimiento_obj.month]} de {fallecimiento_obj.year}"
    else:
        issue_fallecimiento = "-"

    signer_nombre, signer_cargo = _signer(cert)

    return templates.TemplateResponse(
        request,
        "certificates/preview.html",
        {
            "cert": cert,
            "asesor_name": signer_nombre,
            "firma_cargo": signer_cargo,
            "current_user": session.user,
            "csrf_token": generate_csrf_token(session.csrf_secret),
            "can_edit": can_edit,
            "can_review": can_review,
            "total_palabras": total_palabras,
            "issue_day": issue_date_obj.day,
            "issue_month": _MESES[issue_date_obj.month],
            "issue_year": issue_date_obj.year,
            "issue_date": issue_date_obj.strftime("%d/%m/%Y"),
            "issue_fallecimiento": issue_fallecimiento,
            "lineas_servicio": lineas_servicio,
            "entry_date": entry_date,
        },
    )


@router.get("/{cert_id}/pdf")
async def download_certificate_pdf(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    cert = await certificate_service.get_with_asesor(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        certificate_service.assert_can_view(cert, session.user)
    except certificate_service.CertificateServiceError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if cert.status != StatusEnum.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El PDF solo está disponible para solicitudes aprobadas.",
        )

    signer_nombre, signer_cargo = _signer(cert)
    lineas_servicio = (
        await servicio_service.get_lineas_for_cert(
            db, cert.empresa, cert.nombre_servicio, cert.valor_total,
            servicios_json=cert.servicios_json,
        )
        if cert.valor_total
        else None
    )
    pdf_bytes = pdf_service.build_certificate_pdf(
        cert,
        signer_name=signer_nombre,
        signer_cargo=signer_cargo,
        lineas_servicio=lineas_servicio,
    )
    if cert.fallecido_numero_documento:
        pdf_bytes = encrypt_pdf(pdf_bytes, cert.fallecido_numero_documento)
    await log_action(
        db,
        actor_user_id=session.user.id,
        action=AuditActionEnum.CERT_PDF_GENERATED,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=_ip(request),
    )
    await db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_pdf_filename(cert)}"'},
    )


@router.post(
    "/{cert_id}/resend-email",
    dependencies=[Depends(require_role(RoleEnum.REVISOR, RoleEnum.ADMIN)), Depends(verify_csrf)],
)
async def resend_certificate_email(
    cert_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    cert = await certificate_service.get_or_none(db, cert_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if cert.status != StatusEnum.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se puede reenviar el correo de solicitudes aprobadas.",
        )

    email_sent = await certificate_service.send_certificate_email(
        db, cert=cert, actor=session.user, ip_address=_ip(request)
    )

    url = f"/certificates/{cert.id}"
    url += "?msg=Correo+reenviado." if email_sent else "?msg=El+reenv%C3%ADo+del+correo+fall%C3%B3."
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


_GENERIC_MSGS = {"Field required", "String should have at least 1 character"}

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\r\n\t]')


def _pdf_filename(cert) -> str:
    name = (cert.fallecido_nombre_completo or "FALLECIDO").strip().upper()
    name = _UNSAFE_CHARS.sub('', name)
    name = ' '.join(name.split())
    return f"{name}(QEPD).pdf"


def _check_required(form_dict: dict, required_fields: set[str]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for fname in required_fields:
        val = form_dict.get(fname, "")
        if not val or (isinstance(val, str) and not val.strip()):
            errors[fname] = ""
    return errors


def _field_errors(exc: pydantic.ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for e in exc.errors():
        field = str(e["loc"][0]) if e["loc"] else "__root__"
        msg = e["msg"]
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        if msg in _GENERIC_MSGS:
            msg = ""
        errors.setdefault(field, msg)
    return errors
