from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_csrf_token
from app.core.templating import templates
from app.db.session import get_db
from app.dependencies.auth import get_current_session
from app.models.certificate_request import CertificateRequest, StatusEnum
from app.models.session import Session as DbSession
from app.models.user import RoleEnum

router = APIRouter()


@router.get("/")
async def home(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    user = session.user

    # Count certificates per status (scoped to user for Asesor)
    q = select(CertificateRequest.status, func.count().label("n")).group_by(
        CertificateRequest.status
    )
    if user.role == RoleEnum.ASESOR:
        q = q.where(CertificateRequest.asesor_id == user.id)
    elif user.role == RoleEnum.REVISOR:
        q = q.where(CertificateRequest.status != StatusEnum.DRAFT)

    result = await db.execute(q)
    counts = {row.status: row.n for row in result}

    stats = {
        "draft":    counts.get(StatusEnum.DRAFT,    0),
        "pending":  counts.get(StatusEnum.PENDING,  0),
        "approved": counts.get(StatusEnum.APPROVED, 0),
        "rejected": counts.get(StatusEnum.REJECTED, 0),
    }

    # Recent 6 certificates (same scoping)
    rq = select(CertificateRequest).order_by(CertificateRequest.created_at.desc()).limit(6)
    if user.role == RoleEnum.ASESOR:
        rq = rq.where(CertificateRequest.asesor_id == user.id)
    elif user.role == RoleEnum.REVISOR:
        rq = rq.where(CertificateRequest.status != StatusEnum.DRAFT)
    recent_result = await db.execute(rq)
    recent = list(recent_result.scalars().all())

    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "current_user": user,
            "csrf_token": generate_csrf_token(session.csrf_secret),
            "stats": stats,
            "recent": recent,
            "pending_count": stats["pending"],
        },
    )
