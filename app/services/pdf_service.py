import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.certificate_request import CertificateRequest

_styles = getSampleStyleSheet()

_title_style = ParagraphStyle(
    "ClaraTitle",
    parent=_styles["Title"],
    fontSize=18,
    spaceAfter=2,
    alignment=1,  # center
)
_subtitle_style = ParagraphStyle(
    "ClaraSubtitle",
    parent=_styles["Normal"],
    fontSize=10,
    spaceAfter=2,
    alignment=1,
    textColor=colors.grey,
)
_cert_num_style = ParagraphStyle(
    "CertNum",
    parent=_styles["Normal"],
    fontSize=9,
    spaceAfter=2,
    textColor=colors.grey,
)
_heading_style = ParagraphStyle(
    "Heading",
    parent=_styles["Normal"],
    fontSize=13,
    spaceBefore=14,
    spaceAfter=6,
    fontName="Helvetica-Bold",
)
_body_style = ParagraphStyle(
    "Body",
    parent=_styles["Normal"],
    fontSize=10,
    spaceAfter=4,
    leading=14,
)
_services_label_style = ParagraphStyle(
    "ServLabel",
    parent=_styles["Normal"],
    fontSize=10,
    fontName="Helvetica-Bold",
)
_services_value_style = ParagraphStyle(
    "ServValue",
    parent=_styles["Normal"],
    fontSize=10,
    fontName="Helvetica-Bold",
    alignment=2,  # right
)
_total_style = ParagraphStyle(
    "Total",
    parent=_styles["Normal"],
    fontSize=10,
    fontName="Helvetica-Bold",
    spaceBefore=6,
    spaceAfter=6,
)
_iva_style = ParagraphStyle(
    "IVA",
    parent=_styles["Normal"],
    fontSize=8,
    spaceAfter=8,
    textColor=colors.grey,
    leading=11,
)
_footer_style = ParagraphStyle(
    "Footer",
    parent=_styles["Normal"],
    fontSize=9,
    spaceAfter=4,
    leading=12,
)
_sig_name_style = ParagraphStyle(
    "SigName",
    parent=_styles["Normal"],
    fontSize=10,
    fontName="Helvetica-Bold",
    spaceAfter=1,
)
_sig_title_style = ParagraphStyle(
    "SigTitle",
    parent=_styles["Normal"],
    fontSize=9,
    spaceAfter=1,
)

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_larga(d: date) -> str:
    return f"{d.day} de {_MESES[d.month]} de {d.year}"


def _formato_cop(n: int) -> str:
    """Format integer as Colombian peso: 18240000 → '18.240.000'"""
    return f"{n:,}".replace(",", ".")


def _numero_a_palabras(n: int) -> str:
    """Convert a positive integer to Colombian Spanish uppercase words."""
    if n == 0:
        return "CERO"

    unidades = [
        "", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE",
        "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE",
        "DIECIOCHO", "DIECINUEVE",
    ]
    decenas = [
        "", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA",
        "SESENTA", "SETENTA", "OCHENTA", "NOVENTA",
    ]
    centenas = [
        "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS",
        "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS",
    ]

    def _tres(x: int) -> str:
        if x == 0:
            return ""
        if x == 100:
            return "CIEN"
        parts = []
        if x >= 100:
            parts.append(centenas[x // 100])
            x %= 100
        if x >= 20:
            dec = decenas[x // 10]
            rem = x % 10
            parts.append(dec + (" Y " + unidades[rem] if rem else ""))
        elif x > 0:
            parts.append(unidades[x])
        return " ".join(parts)

    parts = []
    if n >= 1_000_000_000:
        g = n // 1_000_000_000
        parts.append(("MIL" if g == 1 else f"{_tres(g)} MIL") + " MILLONES")
        n %= 1_000_000_000
    if n >= 1_000_000:
        m = n // 1_000_000
        parts.append("UN MILLÓN" if m == 1 else f"{_tres(m)} MILLONES")
        n %= 1_000_000
    if n >= 1_000:
        k = n // 1_000
        parts.append("MIL" if k == 1 else f"{_tres(k)} MIL")
        n %= 1_000
    if n > 0:
        parts.append(_tres(n))
    return " ".join(parts)


def build_certificate_pdf(cert: CertificateRequest) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        title=f"Certificado {cert.numero_certificado or cert.id}",
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    empresa = cert.empresa or "RECORDAR"
    story.append(Paragraph(empresa, _title_style))
    story.append(Paragraph("Servicios Exequiales", _subtitle_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 0.2 * cm))

    if cert.numero_certificado:
        story.append(Paragraph(cert.numero_certificado, _cert_num_style))

    # ── Body ──────────────────────────────────────────────────────────────────
    story.append(Paragraph("CERTIFICAMOS", _heading_style))

    fallecimiento = _fecha_larga(cert.fallecido_fecha_fallecimiento) if cert.fallecido_fecha_fallecimiento else "-"
    doc_cliente = cert.cliente_numero_documento or "-"
    doc_fallecido = cert.fallecido_numero_documento or "-"

    body_text = (
        f"Que el (la) señor (a) <b>{cert.cliente_nombre_completo}</b>, "
        f"identificado (a) con la cédula de ciudadanía N° {doc_cliente}; "
        f"titular de los servicios que adquirió en nuestra empresa que se relaciona "
        f"a continuación. Los cuales fueron utilizados con el beneficiario (a) "
        f"<b>{cert.fallecido_nombre_completo}</b> identificado(a) con la cédula de "
        f"ciudadanía N° {doc_fallecido} (Q.E.P.D); "
        f"Fecha de Defunción el día {fallecimiento}."
    )
    story.append(Paragraph(body_text, _body_style))
    story.append(Spacer(1, 0.4 * cm))

    # ── Services ──────────────────────────────────────────────────────────────
    if cert.nombre_servicio or cert.valor_total:
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black))

        services_header = Table(
            [[
                Paragraph("SERVICIOS UTILIZADOS", _services_label_style),
                Paragraph("VALOR", _services_value_style),
            ]],
            colWidths=[12 * cm, 4 * cm],
        )
        services_header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(services_header)
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black))

        valor_str = f"$ {_formato_cop(cert.valor_total)}" if cert.valor_total else "-"
        svc_name = cert.nombre_servicio or ""
        svc_dots = "." * max(1, 60 - len(svc_name))

        services_row = Table(
            [[
                Paragraph(f"{svc_name}{svc_dots}", _body_style),
                Paragraph(valor_str, ParagraphStyle("ValRight", parent=_body_style, alignment=2)),
            ]],
            colWidths=[12 * cm, 4 * cm],
        )
        services_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(services_row)

        if cert.descripcion_servicio:
            story.append(Paragraph(f"({cert.descripcion_servicio})", _body_style))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black))
        story.append(Spacer(1, 0.3 * cm))

        if cert.valor_total:
            palabras = _numero_a_palabras(cert.valor_total)
            total_text = f"TOTAL: {palabras} PESOS M/L (${_formato_cop(cert.valor_total)})"
            story.append(Paragraph(total_text, _total_style))

    # ── IVA exclusion ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Producto Excluido de IVA: Conforme con lo dispuesto por el Artículo 476, numeral 14 "
        "del estatuto tributario, se encuentran excluidos del impuesto sobre las ventas los "
        "Servicios Funerarios, los de Cremación, Inhumación y Exhumación de Cadáveres, Alquiler "
        "y Mantenimiento de Tumbas y Mausoleos.",
        _iva_style,
    ))

    # ── Issue date ────────────────────────────────────────────────────────────
    issue_date = cert.reviewed_at.date() if cert.reviewed_at else date.today()
    footer_text = (
        f"Se expide la presente certificación a solicitud del interesado a los "
        f"{issue_date.day} días del mes de {_MESES[issue_date.month]} de {issue_date.year}."
    )
    if cert.numero_factura:
        footer_text += f" Amparado bajo la Factura N° {cert.numero_factura}"
    elif cert.numero_recibo_caja:
        footer_text += f" Recibo de caja N° {cert.numero_recibo_caja}"
    story.append(Paragraph(footer_text, _footer_style))

    # ── Signature ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.5 * cm))
    story.append(HRFlowable(width=6 * cm, thickness=0.5, color=colors.black, hAlign="LEFT"))
    story.append(Paragraph(cert.asesor.full_name if cert.asesor else "Administrador de Ciudad", _sig_name_style))
    story.append(Paragraph("Administrador de Ciudad", _sig_title_style))
    story.append(Paragraph(issue_date.strftime("%d/%m/%Y"), _sig_title_style))

    doc.build(story)
    return buffer.getvalue()
