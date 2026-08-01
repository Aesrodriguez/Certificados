import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.responses import PlainTextResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.routers import admin, audit, auth, certificates, dashboard

configure_logging()
logger = logging.getLogger(__name__)

if not settings.gmail_configured:
    logger.warning(
        "EMAIL NOT CONFIGURED: set GMAIL_SENDER, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET "
        "and GMAIL_REFRESH_TOKEN in Render environment variables."
    )

app = FastAPI(title="Clara Certificados")

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return PlainTextResponse("Demasiados intentos, intenta de nuevo más tarde.", status_code=429)


# Render terminates TLS at the edge and forwards plain HTTP with
# X-Forwarded-Proto; without this, request.url.scheme is always "http" and
# the HSTS header in SecurityHeadersMiddleware would never be set.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(SecurityHeadersMiddleware)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(audit.router)
app.include_router(certificates.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/debug/gmail")
async def debug_gmail():
    """Temporary: tests Gmail API OAuth2 config. Remove after email is confirmed working."""
    import httpx as _httpx

    result = {
        "gmail_sender": settings.GMAIL_SENDER or "(not set)",
        "client_id_set": bool(settings.GMAIL_CLIENT_ID),
        "client_secret_set": bool(settings.GMAIL_CLIENT_SECRET),
        "refresh_token_set": bool(settings.GMAIL_REFRESH_TOKEN),
    }

    if not settings.gmail_configured:
        result["status"] = "ERROR: faltan variables GMAIL_* en Render"
        return result

    try:
        resp = _httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET,
                "refresh_token": settings.GMAIL_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        if resp.status_code == 200 and resp.json().get("access_token"):
            result["status"] = "OK - token de acceso obtenido correctamente"
        else:
            result["status"] = f"ERROR ({resp.status_code}): {resp.text}"
    except Exception as e:
        result["status"] = f"ERROR: {type(e).__name__}: {e}"

    return result
