import asyncio
import base64
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import resend

from app.core.config import settings
from app.models.certificate_request import CertificateRequest


class EmailDeliveryError(Exception):
    """Raised when all email delivery methods fail."""


def _smtp_available() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_PASSWORD)


def _send_smtp_sync(to: str, subject: str, html: str, attachment: tuple[str, bytes] | None = None) -> None:
    """Synchronous SMTP send — called via asyncio.to_thread to avoid blocking."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"Clara Certificados <{settings.SMTP_USER}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    if attachment:
        filename, data = attachment
        part = MIMEApplication(data, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, [to], msg.as_bytes())


async def _send_smtp(to: str, subject: str, html: str, attachment: tuple[str, bytes] | None = None) -> None:
    await asyncio.to_thread(_send_smtp_sync, to, subject, html, attachment)


def _send_resend(to: str, subject: str, html: str, attachment: tuple[str, bytes] | None = None) -> None:
    resend.api_key = settings.RESEND_API_KEY
    payload: dict = {
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if attachment:
        filename, data = attachment
        payload["attachments"] = [{"filename": filename, "content": base64.b64encode(data).decode()}]
    resend.Emails.send(payload)


async def _send(to: str, subject: str, html: str, attachment: tuple[str, bytes] | None = None) -> None:
    """Try SMTP first, fall back to Resend. Raises EmailDeliveryError if both fail."""
    if _smtp_available():
        try:
            await _send_smtp(to, subject, html, attachment)
            return
        except Exception as exc:
            if not settings.RESEND_API_KEY:
                raise EmailDeliveryError(f"SMTP failed: {exc}") from exc

    if settings.RESEND_API_KEY:
        try:
            _send_resend(to, subject, html, attachment)
            return
        except Exception as exc:
            raise EmailDeliveryError(f"Resend failed: {exc}") from exc

    raise EmailDeliveryError("No email provider configured (set SMTP_USER/SMTP_PASSWORD or RESEND_API_KEY).")


# ── Public API ────────────────────────────────────────────────────────────────

def send_certificate_email(cert: CertificateRequest, pdf_bytes: bytes) -> None:
    html = f"""
    <p>Estimado/a {cert.cliente_nombre_completo},</p>
    <p>Adjunto encontrará el certificado de servicios exequiales correspondiente a
    <strong>{cert.fallecido_nombre_completo}</strong>.</p>
    <p>Este es un mensaje generado automáticamente, por favor no responda a este correo.</p>
    <p>Clara Certificados</p>
    """
    filename = f"certificado_{cert.id}.pdf"
    subject = f"Certificado exequial - {cert.fallecido_nombre_completo}"
    try:
        asyncio.get_event_loop().run_until_complete(
            _send(cert.cliente_email, subject, html, (filename, pdf_bytes))
        )
    except RuntimeError:
        # Already inside an event loop (FastAPI context) — run synchronously via thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _send(cert.cliente_email, subject, html, (filename, pdf_bytes)))
            future.result()


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
