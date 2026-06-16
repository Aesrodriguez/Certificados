from fastapi import APIRouter, Depends, Request

from app.core.security import generate_csrf_token
from app.core.templating import templates
from app.dependencies.auth import get_current_session
from app.models.session import Session as DbSession

router = APIRouter()


@router.get("/")
async def home(request: Request, session: DbSession = Depends(get_current_session)):
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "current_user": session.user,
            "csrf_token": generate_csrf_token(session.csrf_secret),
        },
    )
