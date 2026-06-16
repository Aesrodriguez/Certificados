import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditActionEnum
from app.models.certificate_request import CertificateRequest, StatusEnum
from app.models.user import RoleEnum, User
from app.schemas.certificate_request import CertificateRequestIn
from app.services import email_service, pdf_service
from app.services.audit_service import log_action

EDITABLE_STATUSES = {StatusEnum.DRAFT, StatusEnum.REJECTED}


class CertificateServiceError(Exception):
    """Raised for certificate workflow violations meant to be shown to the user."""


async def list_for_user(db: AsyncSession, user: User) -> list[CertificateRequest]:
    query = select(CertificateRequest).order_by(CertificateRequest.created_at.desc())
    if user.role == RoleEnum.ASESOR:
        query = query.where(CertificateRequest.asesor_id == user.id)
    elif user.role == RoleEnum.REVISOR:
        query = query.where(CertificateRequest.status != StatusEnum.DRAFT)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_or_none(db: AsyncSession, cert_id: uuid.UUID) -> CertificateRequest | None:
    result = await db.execute(select(CertificateRequest).where(CertificateRequest.id == cert_id))
    return result.scalar_one_or_none()


def assert_can_view(cert: CertificateRequest, user: User) -> None:
    if user.role == RoleEnum.ASESOR and cert.asesor_id != user.id:
        raise CertificateServiceError("No tienes acceso a esta solicitud.")
    if user.role == RoleEnum.REVISOR and cert.status == StatusEnum.DRAFT:
        raise CertificateServiceError("Esta solicitud todavía no ha sido enviada a revisión.")


def assert_can_edit(cert: CertificateRequest, user: User) -> None:
    if cert.asesor_id != user.id:
        raise CertificateServiceError("No tienes acceso a esta solicitud.")
    if cert.status not in EDITABLE_STATUSES:
        raise CertificateServiceError("Esta solicitud ya no se puede editar en su estado actual.")


async def create_draft(
    db: AsyncSession, *, asesor: User, data: CertificateRequestIn, ip_address: str | None
) -> CertificateRequest:
    cert = CertificateRequest(asesor_id=asesor.id, status=StatusEnum.DRAFT, **data.model_dump())
    db.add(cert)
    await db.flush()
    await log_action(
        db,
        actor_user_id=asesor.id,
        action=AuditActionEnum.CERT_CREATED,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=ip_address,
    )
    await db.commit()
    return cert


async def update_draft(
    db: AsyncSession,
    *,
    cert: CertificateRequest,
    asesor: User,
    data: CertificateRequestIn,
    ip_address: str | None,
) -> None:
    assert_can_edit(cert, asesor)
    for field, value in data.model_dump().items():
        setattr(cert, field, value)
    await log_action(
        db,
        actor_user_id=asesor.id,
        action=AuditActionEnum.CERT_UPDATED,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=ip_address,
    )
    await db.commit()


async def submit(
    db: AsyncSession, *, cert: CertificateRequest, asesor: User, ip_address: str | None
) -> None:
    assert_can_edit(cert, asesor)
    cert.status = StatusEnum.PENDING
    cert.submitted_at = datetime.now(timezone.utc)
    cert.rejection_comment = None
    await log_action(
        db,
        actor_user_id=asesor.id,
        action=AuditActionEnum.CERT_SUBMITTED,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=ip_address,
    )
    await db.commit()


def assert_can_review(cert: CertificateRequest, revisor: User) -> None:
    if revisor.role != RoleEnum.REVISOR:
        raise CertificateServiceError("Solo un Revisor puede aprobar o rechazar solicitudes.")
    if cert.status != StatusEnum.PENDING:
        raise CertificateServiceError("Esta solicitud no está pendiente de revisión.")


async def approve(
    db: AsyncSession, *, cert: CertificateRequest, revisor: User, ip_address: str | None
) -> bool:
    """Approve the request and attempt to email the certificate.

    Returns True if the email was sent successfully. The approval itself is
    committed first and is never rolled back due to an email failure — email
    delivery is a retriable side effect, not the source of truth.
    """
    assert_can_review(cert, revisor)
    cert.status = StatusEnum.APPROVED
    cert.revisor_id = revisor.id
    cert.reviewed_at = datetime.now(timezone.utc)
    cert.rejection_comment = None
    await log_action(
        db,
        actor_user_id=revisor.id,
        action=AuditActionEnum.CERT_APPROVED,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=ip_address,
    )
    await db.commit()

    return await send_certificate_email(db, cert=cert, actor=revisor, ip_address=ip_address)


async def send_certificate_email(
    db: AsyncSession, *, cert: CertificateRequest, actor: User, ip_address: str | None
) -> bool:
    pdf_bytes = pdf_service.build_certificate_pdf(cert)
    await log_action(
        db,
        actor_user_id=actor.id,
        action=AuditActionEnum.CERT_PDF_GENERATED,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=ip_address,
    )

    try:
        email_service.send_certificate_email(cert, pdf_bytes)
    except email_service.EmailDeliveryError as exc:
        await log_action(
            db,
            actor_user_id=actor.id,
            action=AuditActionEnum.CERT_EMAIL_FAILED,
            entity_type="certificate_request",
            entity_id=cert.id,
            ip_address=ip_address,
            metadata={"error": str(exc)},
        )
        await db.commit()
        return False

    await log_action(
        db,
        actor_user_id=actor.id,
        action=AuditActionEnum.CERT_EMAIL_SENT,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=ip_address,
    )
    await db.commit()
    return True


async def reject(
    db: AsyncSession,
    *,
    cert: CertificateRequest,
    revisor: User,
    comment: str,
    ip_address: str | None,
) -> None:
    assert_can_review(cert, revisor)
    if not comment.strip():
        raise CertificateServiceError("Debes indicar un motivo para rechazar la solicitud.")

    cert.status = StatusEnum.REJECTED
    cert.revisor_id = revisor.id
    cert.reviewed_at = datetime.now(timezone.utc)
    cert.rejection_comment = comment.strip()
    await log_action(
        db,
        actor_user_id=revisor.id,
        action=AuditActionEnum.CERT_REJECTED,
        entity_type="certificate_request",
        entity_id=cert.id,
        ip_address=ip_address,
        metadata={"comment": comment.strip()},
    )
    await db.commit()
