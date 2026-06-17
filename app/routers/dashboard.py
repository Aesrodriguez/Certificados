from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.dependencies.auth import get_current_session
from app.models.session import Session as DbSession
from app.models.user import RoleEnum

router = APIRouter()


@router.get("/")
async def home(request: Request, session: DbSession = Depends(get_current_session)):
    """Redirect to the most relevant page based on the user's role."""
    if session.user.role in (RoleEnum.ASESOR, RoleEnum.ADMIN):
        return RedirectResponse(url="/certificates/new", status_code=303)
    # Revisor → certificate list (only sees pending/approved/rejected)
    return RedirectResponse(url="/certificates", status_code=303)
