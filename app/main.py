import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import PlainTextResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import settings
from app.core.errors import registrar_manejadores
from app.core.logging_config import configure_logging
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.routers import admin, audit, auth, certificates, dashboard, marca, reportes, servicios

configure_logging()
logger = logging.getLogger(__name__)

if not settings.gmail_configured:
    logger.warning(
        "EMAIL NOT CONFIGURED: set GMAIL_SENDER, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET "
        "and GMAIL_REFRESH_TOKEN in the hosting environment variables (Render or Vercel)."
    )

app = FastAPI(title="Clara Certificados")

app.state.limiter = limiter

# Pantallas de error (404, 403, 429, 500, 503…) en vez de las respuestas vacías.
registrar_manejadores(app)


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
app.include_router(servicios.router)
app.include_router(reportes.router)
app.include_router(marca.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/keepalive", include_in_schema=False)
@limiter.limit("30/minute")
async def keepalive(request: Request):
    """Lo visita un monitor externo cada pocos minutos para que Render (plan gratis)
    no duerma el servidor y Supabase no pause la base de datos por inactividad.
    No expone datos: solo hace SELECT 1. /healthz queda sin BD para el chequeo de Render."""
    from sqlalchemy import text

    from app.db.session import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logging.getLogger(__name__).exception("keepalive: la base de datos no respondió")
        return PlainTextResponse("db error", status_code=503)
    return PlainTextResponse("ok")


