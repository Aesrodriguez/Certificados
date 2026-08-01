import asyncio
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.models.certificate_request import CertificateRequest

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when email delivery fails."""


def _send_gmail_sync(to: str, subject: str, html: str, attachment: tuple[str, bytes] | None = None) -> None:
    """Synchronous Gmail SMTP send — called via asyncio.to_thread to avoid blocking the event loop."""
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

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_USER, [to], msg.as_bytes())


async def _send(to: str, subject: str, html: str, attachment: tuple[str, bytes] | None = None) -> None:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise EmailDeliveryError(
            "Gmail not configured: set SMTP_USER (tu correo Gmail) and SMTP_PASSWORD "
            "(App Password de Gmail) in Render environment variables."
        )
    try:
        await asyncio.to_thread(_send_gmail_sync, to, subject, html, attachment)
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailDeliveryError(
            f"Gmail authentication failed — verify SMTP_USER and SMTP_PASSWORD (App Password): {exc}"
        ) from exc
    except Exception as exc:
        raise EmailDeliveryError(f"Gmail send failed: {exc}") from exc


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
