import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.certificate_request import CertificateRequest

_styles = getSampleStyleSheet()
_title_style = ParagraphStyle(
    "ClaraTitle", parent=_styles["Title"], fontSize=16, spaceAfter=4
)
_section_style = ParagraphStyle(
    "ClaraSection", parent=_styles["Heading3"], fontSize=11, spaceBefore=12, spaceAfter=4
)
_body_style = _styles["BodyText"]


def _info_table(rows: list[tuple[str, str]]) -> Table:
    table = Table(
        [[Paragraph(f"<b>{label}</b>", _body_style), Paragraph(value or "-", _body_style)] for label, value in rows],
        colWidths=[5 * cm, 11 * cm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]
        )
    )
    return table


def build_certificate_pdf(cert: CertificateRequest) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title=f"Certificado {cert.id}",
    )

    story = [
        Paragraph("Clara", _title_style),
        Paragraph("Certificado de Servicios Exequiales", _styles["Heading2"]),
        Spacer(1, 0.3 * cm),
        Paragraph(f"Certificado N.º {cert.id}", _body_style),
        Paragraph(f"Fecha de emisión: {cert.reviewed_at.strftime('%Y-%m-%d') if cert.reviewed_at else '-'}", _body_style),
        Spacer(1, 0.4 * cm),
        Paragraph("Datos del cliente", _section_style),
        _info_table(
            [
                ("Nombre completo", cert.cliente_nombre_completo),
                ("Documento", f"{cert.cliente_tipo_documento} {cert.cliente_numero_documento}"),
                ("Teléfono", cert.cliente_telefono),
                ("Correo", cert.cliente_email),
                ("Parentesco", cert.cliente_parentesco),
                ("Dirección", ", ".join(filter(None, [cert.cliente_direccion, cert.cliente_ciudad]))),
            ]
        ),
        Paragraph("Datos del fallecido", _section_style),
        _info_table(
            [
                ("Nombre completo", cert.fallecido_nombre_completo),
                ("Documento", f"{cert.fallecido_tipo_documento} {cert.fallecido_numero_documento}"),
                ("Fecha de nacimiento", str(cert.fallecido_fecha_nacimiento or "-")),
                ("Fecha de fallecimiento", str(cert.fallecido_fecha_fallecimiento)),
                ("Lugar de fallecimiento", cert.fallecido_lugar_fallecimiento),
                ("Causa de fallecimiento", cert.fallecido_causa_fallecimiento),
                ("N.º acta de defunción", cert.fallecido_numero_acta_defuncion),
            ]
        ),
        Paragraph("Otros datos", _section_style),
        _info_table(
            [
                ("Plan o póliza", cert.plan_o_poliza),
                ("Observaciones", cert.observaciones),
            ]
        ),
        Spacer(1, 1 * cm),
        Paragraph(
            "Este certificado se genera electrónicamente y es válido sin firma manuscrita.",
            ParagraphStyle("footer", parent=_body_style, fontSize=8, textColor=colors.grey),
        ),
    ]

    doc.build(story)
    return buffer.getvalue()
