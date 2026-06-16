from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.responses import PlainTextResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.logging_config import configure_logging
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.routers import admin, audit, auth, certificates, dashboard

configure_logging()

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
