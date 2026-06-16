from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import generate_csrf_token
from app.core.templating import templates
from app.db.session import get_db
from app.dependencies.auth import get_current_session, require_role
from app.models.audit_log import AuditLog
from app.models.session import Session as DbSession
from app.models.user import RoleEnum

router = APIRouter(
    prefix="/admin/audit-log", dependencies=[Depends(require_role(RoleEnum.ADMIN))]
)


@router.get("")
async def list_audit_log(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    result = await db.execute(
        select(AuditLog)
        .options(selectinload(AuditLog.actor))
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    )
    logs = list(result.scalars().all())
    return templates.TemplateResponse(
        request,
        "audit/log_list.html",
        {
            "current_user": session.user,
            "csrf_token": generate_csrf_token(session.csrf_secret),
            "logs": logs,
        },
    )
