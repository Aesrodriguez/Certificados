import uuid

import pydantic
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services import certificate_service, pdf_service
from app.services.audit_service import log_action

router = APIRouter(
    prefix="/certificates",
    dependencies=[Depends(require_role(RoleEnum.ADMIN, RoleEnum.ASESOR, RoleEnum.REVISOR))],
)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _ctx(session: DbSession, **extra) -> dict:
    return {
        "current_user": session.user,
        "csrf_token": generate_csrf_token(session.csrf_secret),
        **extra,
    }


@router.get("")
async def list_certificates(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    certs = await certificate_service.list_for_user(db, session.user)
    return templates.TemplateResponse(
        request, "certificates/list.html", _ctx(session, certs=certs)
    )


@router.get("/new", dependencies=[Depends(require_role(RoleEnum.ASESOR))])
async def new_certificate_form(
    request: Request,
    session: DbSession = Depends(get_current_session),
):
    return templates.TemplateResponse(
        request,
        "certificates/form.html",
        _ctx(session, cert=None, error=None, form_action="/certificates"),
    )


@router.post("", dependencies=[Depends(require_role(RoleEnum.ASESOR)), Depends(verify_csrf)])
async def create_certificate(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    form = await request.form()
    try:
        data = CertificateRequestIn.model_validate(dict(form))
    except pydantic.ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "certificates/form.html",
            _ctx(
                session,
                cert=dict(form),
                error=_format_errors(exc),
                form_action="/certificates",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    cert = await certificate_service.create_draft(
        db, asesor=session.user, data=data, ip_address=_ip(request)
    )
    return RedirectResponse(url=f"/certificates/{cert.id}", status_code=status.HTTP_303_SEE_OTHER)


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

    await log_action(
        db,
        actor_user_id=session.user.id,
        action=AuditActionEnum.CERT_VIEWED,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=_ip(request),
    )
    await db.commit()

    can_edit = cert.asesor_id == session.user.id and cert.status in certificate_service.EDITABLE_STATUSES
    can_review = session.user.role == RoleEnum.REVISOR and cert.status.value == "pending"
    return templates.TemplateResponse(
        request,
        "certificates/detail.html",
        _ctx(session, cert=cert, can_edit=can_edit, can_review=can_review),
    )


@router.get("/{cert_id}/edit", dependencies=[Depends(require_role(RoleEnum.ASESOR))])
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

    return templates.TemplateResponse(
        request,
        "certificates/form.html",
        _ctx(session, cert=cert, error=None, form_action=f"/certificates/{cert.id}"),
    )


@router.post(
    "/{cert_id}", dependencies=[Depends(require_role(RoleEnum.ASESOR)), Depends(verify_csrf)]
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
    try:
        data = CertificateRequestIn.model_validate(dict(form))
    except pydantic.ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "certificates/form.html",
            _ctx(
                session,
                cert=dict(form),
                error=_format_errors(exc),
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
    "/{cert_id}/submit",
    dependencies=[Depends(require_role(RoleEnum.ASESOR)), Depends(verify_csrf)],
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
    dependencies=[Depends(require_role(RoleEnum.REVISOR)), Depends(verify_csrf)],
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
    dependencies=[Depends(require_role(RoleEnum.REVISOR)), Depends(verify_csrf)],
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


@router.get("/{cert_id}/pdf")
async def download_certificate_pdf(
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
    if cert.status != StatusEnum.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El PDF solo está disponible para solicitudes aprobadas.",
        )

    pdf_bytes = pdf_service.build_certificate_pdf(cert)
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
        headers={"Content-Disposition": f'attachment; filename="certificado_{cert.id}.pdf"'},
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


def _format_errors(exc: pydantic.ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
