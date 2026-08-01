"""
Email delivery via Gmail API (OAuth2 + HTTPS).

Why not SMTP: Render free tier blocks outbound ports 25/465/587.
Gmail API communicates over HTTPS (port 443) which is always open.
"""
import asyncio
import base64
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.core.config import settings
from app.models.certificate_request import CertificateRequest

logger = logging.getLogger(__name__)

_GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class EmailDeliveryError(Exception):
    """Raised when email delivery fails."""


def _build_mime(
    to: str,
    subject: str,
    html: str,
    attachment: tuple[str, bytes] | None = None,
) -> bytes:
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"Clara Certificados <{settings.GMAIL_SENDER}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    if attachment:
        filename, data = attachment
        part = MIMEApplication(data, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    return msg.as_bytes()


def _send_sync(to: str, subject: str, html: str, attachment: tuple[str, bytes] | None = None) -> None:
    """Synchronous Gmail API send — runs in a thread via asyncio.to_thread."""
    # Step 1: refresh access token
    token_resp = httpx.post(
        _GMAIL_TOKEN_URL,
        data={
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "refresh_token": settings.GMAIL_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    if token_resp.status_code != 200:
        raise EmailDeliveryError(
            f"Gmail token refresh failed ({token_resp.status_code}): {token_resp.text}"
        )
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise EmailDeliveryError(f"No access_token in Gmail response: {token_resp.text}")

    # Step 2: send via Gmail API
    raw = base64.urlsafe_b64encode(_build_mime(to, subject, html, attachment)).decode()
    send_resp = httpx.post(
        _GMAIL_SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        json={"raw": raw},
        timeout=30,
    )
    if send_resp.status_code not in (200, 201):
        raise EmailDeliveryError(
            f"Gmail send failed ({send_resp.status_code}): {send_resp.text}"
        )


async def _send(to: str, subject: str, html: str, attachment: tuple[str, bytes] | None = None) -> None:
    if not settings.gmail_configured:
        raise EmailDeliveryError(
            "Gmail API not configured. Set GMAIL_SENDER, GMAIL_CLIENT_ID, "
            "GMAIL_CLIENT_SECRET and GMAIL_REFRESH_TOKEN in Render environment variables."
        )
    await asyncio.to_thread(_send_sync, to, subject, html, attachment)


# ── Public API ────────────────────────────────────────────────────────────────

async def send_certificate_email_async(cert: CertificateRequest, pdf_bytes: bytes) -> None:
    html = f"""
    <p>Estimado/a {cert.cliente_nombre_completo},</p>
    <p>Adjunto encontrará el certificado de servicios exequiales correspondiente a
    <strong>{cert.fallecido_nombre_completo}</strong>.</p>
    <p>Este es un mensaje generado automáticamente, por favor no responda a este correo.</p>
    <p>Clara Certificados</p>
    """
    filename = f"certificado_{cert.id}.pdf"
    subject = f"Certificado exequial - {cert.fallecido_nombre_completo}"
    await _send(cert.cliente_email, subject, html, (filename, pdf_bytes))


async def send_password_reset_email(to_email: str, full_name: str, reset_url: str) -> None:
    html = f"""
    <p>Hola {full_name},</p>
    <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta en
    <strong>Clara Certificados</strong>.</p>
    <p>
      <a href="{reset_url}" style="
        display:inline-block;padding:10px 20px;background:#0d6efd;
        color:#fff;text-decoration:none;border-radius:4px;">
        Restablecer contraseña
      </a>
    </p>
    <p>Este enlace es válido por <strong>30 minutos</strong>.<br>
    Si no solicitaste esto, puedes ignorar este mensaje.</p>
    <p>Clara Certificados</p>
    """
    await _send(to_email, "Restablecer contraseña - Clara Certificados", html)
