import io
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.models.certificate_request import CertificateRequest

_STATIC = Path(__file__).resolve().parent.parent / "static" / "img"
_LETTERHEAD = str(_STATIC / "letterhead.jpg")
_SIGNATURE = str(_STATIC / "signature.png")

# ── Page geometry matched to the letterhead template ──────────────────────────
# Letter page: 21.59 cm × 27.94 cm
# Letterhead has: header ~4.5 cm (logo + green curves), footer ~3 cm
_PAGE_W, _PAGE_H = letter
_TOP_MARGIN    = 4.5 * cm
_BOTTOM_MARGIN = 3.2 * cm
_LEFT_MARGIN   = 3.0 * cm
_RIGHT_MARGIN  = 2.5 * cm

# ── Styles ────────────────────────────────────────────────────────────────────
_styles = getSampleStyleSheet()

_cert_num = ParagraphStyle("CertNum",   parent=_styles["Normal"], fontSize=9,
                           textColor=colors.HexColor("#555555"), spaceAfter=6)
_heading  = ParagraphStyle("Heading",   parent=_styles["Normal"], fontSize=13,
                           fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=8)
_body     = ParagraphStyle("Body",      parent=_styles["Normal"], fontSize=10,
                           leading=16, spaceAfter=10, alignment=4)  # justified
_svc_bold = ParagraphStyle("SvcBold",  parent=_styles["Normal"], fontSize=10,
                           fontName="Helvetica-Bold")
_svc_r    = ParagraphStyle("SvcRight", parent=_styles["Normal"], fontSize=10,
                           fontName="Helvetica-Bold", alignment=2)
_total    = ParagraphStyle("Total",    parent=_styles["Normal"], fontSize=10,
                           fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=8)
_iva      = ParagraphStyle("IVA",      parent=_styles["Normal"], fontSize=8,
                           textColor=colors.HexColor("#444444"), leading=11,
                           spaceAfter=10, alignment=4)
_footer_p = ParagraphStyle("FooterP",  parent=_styles["Normal"], fontSize=10,
                           leading=14, spaceAfter=4, alignment=4)
_sig_name = ParagraphStyle("SigName",  parent=_styles["Normal"], fontSize=10,
                           fontName="Helvetica-Bold", spaceAfter=1)
_sig_role = ParagraphStyle("SigRole",  parent=_styles["Normal"], fontSize=9,
                           spaceAfter=1)

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_larga(d: date) -> str:
    return f"{d.day} de {_MESES[d.month]} de {d.year}"


def _formato_cop(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _numero_a_palabras(n: int) -> str:
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


def _draw_letterhead(canvas, doc):
    """Draw the GRUPO RECORDAR letterhead as full-page background on every page."""
    canvas.saveState()
    canvas.drawImage(_LETTERHEAD, 0, 0, width=_PAGE_W, height=_PAGE_H,
                     preserveAspectRatio=False)
    canvas.restoreState()


def build_certificate_pdf(cert: CertificateRequest) -> bytes:
    buffer = io.BytesIO()

    frame = Frame(
        _LEFT_MARGIN,
        _BOTTOM_MARGIN,
        _PAGE_W - _LEFT_MARGIN - _RIGHT_MARGIN,
        _PAGE_H - _TOP_MARGIN - _BOTTOM_MARGIN,
        id="main",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    page_template = PageTemplate(
        id="main",
        frames=[frame],
        onPage=_draw_letterhead,
    )
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        pageTemplates=[page_template],
        title=f"Certificado {cert.numero_certificado or cert.id}",
        leftMargin=_LEFT_MARGIN,
        rightMargin=_RIGHT_MARGIN,
        topMargin=_TOP_MARGIN,
        bottomMargin=_BOTTOM_MARGIN,
    )

    story: list = []

    # ── Certificate reference number ──────────────────────────────────────────
    if cert.numero_certificado:
        story.append(Paragraph(cert.numero_certificado, _cert_num))

    # ── CERTIFICAMOS heading ──────────────────────────────────────────────────
    story.append(Paragraph("CERTIFICAMOS", _heading))

    # ── Body paragraph ────────────────────────────────────────────────────────
    fallecimiento = _fecha_larga(cert.fallecido_fecha_fallecimiento) if cert.fallecido_fecha_fallecimiento else "-"
    body_text = (
        f"Que el (la) señor (a) <b>{cert.cliente_nombre_completo}</b>, "
        f"identificado (a) con la cédula de ciudadanía N° {cert.cliente_numero_documento}; "
        f"titular de los servicios que adquirió en nuestra empresa que se relaciona "
        f"a continuación. Los cuales fueron utilizados con el beneficiario (a) "
        f"<b>{cert.fallecido_nombre_completo}</b> identificado(a) con la cédula de "
        f"ciudadanía N° {cert.fallecido_numero_documento} (Q.E.P.D); "
        f"Fecha de Defunción el día {fallecimiento}."
    )
    story.append(Paragraph(body_text, _body))
    story.append(Spacer(1, 0.3 * cm))

    # ── Services table ────────────────────────────────────────────────────────
    if cert.nombre_servicio or cert.valor_total:
        content_width = _PAGE_W - _LEFT_MARGIN - _RIGHT_MARGIN
        val_col = 4 * cm
        svc_col = content_width - val_col

        valor_str = f"$ {_formato_cop(cert.valor_total)}" if cert.valor_total else "-"
        svc_name = (cert.nombre_servicio or "").upper()

        # Header row
        header = Table(
            [[Paragraph("SERVICIOS UTILIZADOS", _svc_bold),
              Paragraph("VALOR", _svc_r)]],
            colWidths=[svc_col, val_col],
        )
        header.setStyle(TableStyle([
            ("LINEABOVE",  (0, 0), (-1, 0), 0.5, colors.black),
            ("LINEBELOW",  (0, 0), (-1, 0), 0.5, colors.black),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(header)

        # Service row — dotted leader between name and price
        dots = "." * max(4, int((svc_col / (0.22 * cm)) - len(svc_name)))
        svc_row = Table(
            [[Paragraph(f"{svc_name}{dots}", _body),
              Paragraph(valor_str, _svc_r)]],
            colWidths=[svc_col, val_col],
        )
        svc_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(svc_row)

        if cert.descripcion_servicio:
            story.append(Paragraph(f"({cert.descripcion_servicio})", _body))

        # Closing rule
        closing = Table([[""]], colWidths=[content_width])
        closing.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(closing)
        story.append(Spacer(1, 0.3 * cm))

        if cert.valor_total:
            palabras = _numero_a_palabras(cert.valor_total)
            story.append(Paragraph(
                f"TOTAL: {palabras} PESOS M/L (${_formato_cop(cert.valor_total)})",
                _total,
            ))

    # ── IVA exclusion ─────────────────────────────────────────────────────────
    story.append(Paragraph(
        "Producto Excluido de IVA: Conforme con lo dispuesto por el Artículo 476, numeral 14 "
        "del estatuto tributario, se encuentran excluidos del impuesto sobre las ventas los "
        "Servicios Funerarios, los de Cremación, Inhumación y Exhumación de Cadáveres, Alquiler "
        "y Mantenimiento de Tumbas y Mausoleos.",
        _iva,
    ))

    # ── Issue paragraph ───────────────────────────────────────────────────────
    issue = cert.reviewed_at.date() if cert.reviewed_at else date.today()
    footer_text = (
        f"Se expide la presente certificación a solicitud del interesado a los "
        f"{issue.day} días del mes de {_MESES[issue.month]} de {issue.year}."
    )
    if cert.numero_factura:
        footer_text += f" Amparado bajo la Factura N° {cert.numero_factura}"
    elif cert.numero_recibo_caja:
        footer_text += f" Recibo de caja N° {cert.numero_recibo_caja}"
    story.append(Paragraph(footer_text, _footer_p))

    # ── Signature block ───────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0 * cm))
    if Path(_SIGNATURE).exists():
        sig_img = Image(_SIGNATURE, width=5 * cm, height=2 * cm)
        sig_img.hAlign = "LEFT"
        story.append(sig_img)
    else:
        story.append(Spacer(1, 2 * cm))

    asesor_name = cert.asesor.full_name if cert.asesor else "Administrador de Ciudad"
    story.append(Paragraph(asesor_name, _sig_name))
    story.append(Paragraph("Administrador de Ciudad", _sig_role))
    story.append(Paragraph(issue.strftime("%d/%m/%Y"), _sig_role))

    doc.build(story)
    return buffer.getvalue()
