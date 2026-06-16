import base64

import resend

from app.core.config import settings
from app.models.certificate_request import CertificateRequest


class EmailDeliveryError(Exception):
    """Raised when Resend fails to accept/send the certificate email."""


def _render_email_html(cert: CertificateRequest) -> str:
    return f"""
    <p>Estimado/a {cert.cliente_nombre_completo},</p>
    <p>Adjunto encontrará el certificado de servicios exequiales correspondiente a
    {cert.fallecido_nombre_completo}.</p>
    <p>Este es un mensaje generado automáticamente, por favor no responda a este correo.</p>
    <p>Clara</p>
    """


def send_certificate_email(cert: CertificateRequest, pdf_bytes: bytes) -> None:
    resend.api_key = settings.RESEND_API_KEY
    try:
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": [cert.cliente_email],
                "subject": f"Certificado exequial - {cert.fallecido_nombre_completo}",
                "html": _render_email_html(cert),
                "attachments": [
                    {
                        "filename": f"certificado_{cert.id}.pdf",
                        "content": base64.b64encode(pdf_bytes).decode(),
                    }
                ],
            }
        )
    except Exception as exc:
        raise EmailDeliveryError(str(exc)) from exc
