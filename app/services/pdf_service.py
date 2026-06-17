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


# ── Desglose de servicios por empresa + producto ──────────────────────────────
# Cada entrada: (nombre_del_servicio, porcentaje_decimal)
# Los porcentajes suman 1.0 en cada grupo.

_REC_STD = [  # RECORDAR — Servicio Funerario estándar
    ("Traslado del cuerpo dentro del perímetro urbano", 0.04),
    ("Preparación normal del cuerpo", 0.09),
    ("Suministro del féretro según la Alternativa seleccionada", 0.41),
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.03),
    ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
    ("Cafeteria (Bebidas calientes en sala)", 0.05),
    ("Carteles Virtuales", 0.01),
    ("Trámites civiles y legales ante autoridad competente (Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
    ("Velación por 24 horas", 0.31),
]

_REC_TRANSP = [  # RECORDAR — Solo transporte, velación y restos
    ("Traslado terrestre de la persona fallecida al parque cementerio Jardines de Eternidad sede norte", 0.30),
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.22),
    ("Cafeteria (Bebidas calientes en sala)", 0.05),
    ("Carteles Virtuales", 0.01),
    ("Velación por 24 horas", 0.42),
]

_REC_TRANSP_MISA = [  # RECORDAR — Solo transporte, velación, misa y restos
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.50),
    ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.04),
    ("Cafeteria (Bebidas calientes en sala)", 0.05),
    ("Carteles Virtuales", 0.01),
    ("Velación por 24 horas", 0.40),
]

def _pyf_std(cofre_nombre: str) -> list:
    """Plantilla estándar PYF (Gran Extra / Estilo J / K…), solo cambia el cofre."""
    return [
        ("Recogida del cuerpo dentro del perímetro urbano", 0.04),
        ("Preparación normal del cuerpo", 0.09),
        (cofre_nombre, 0.41),
        ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.03),
        ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
        ("Cafeteria (Bebidas calientes en sala)", 0.05),
        ("Carteles Virtuales", 0.01),
        ("Trámites civiles y legales ante autoridad competente (Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
        ("Velación normal (24 horas)", 0.31),
    ]

_PYF_CREMACION = [  # PYF — Cremación integrada
    ("Recogida del cuerpo dentro del perímetro urbano", 0.04),
    ("Preparación normal del cuerpo", 0.09),
    ('Cofre funebre "L" o el equivalente a talla y peso del fallecido', 0.41),
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo (Carroza Funebre)", 0.03),
    ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
    ("Cafeteria (Bebidas calientes en sala)", 0.05),
    ("Carteles Virtuales", 0.01),
    ("Trámites civiles y legales ante autoridad competente (Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
    ("Velación normal (24 horas)", 0.21),
    ("Reducción del cuerpo a Cenizas por medio del calor", 0.10),
]

# Tabla de búsqueda: (fragmento_empresa, fragmento_servicio) → desglose
# La empresa y el nombre de servicio se comparan en minúsculas (in).
_BREAKDOWN_TABLE: list[tuple[str, str, list]] = [
    # RECORDAR
    ("recordar", "transporte velacion misa", _REC_TRANSP_MISA),
    ("recordar", "transporte velacion",      _REC_TRANSP),
    ("recordar", "",                          _REC_STD),   # catch-all RECORDAR
    # PARQUES Y FUNERARIAS
    ("parques",  "cremacion",    _PYF_CREMACION),
    ("parques",  "gran extra",   _pyf_std('Cofre funebre "Gran Extra" o el equivalente a talla y peso del fallecido')),
    ("parques",  "estilo j",     _pyf_std('Cofre funebre "J" o el equivalente a talla y peso del fallecido')),
    ("parques",  "estilo k",     _pyf_std('Cofre funebre "K" o el equivalente a talla y peso del fallecido')),
    ("parques",  "estilo l",     _pyf_std('Cofre funebre "L" o el equivalente a talla y peso del fallecido')),
    ("parques",  "",             _pyf_std('Cofre funebre según la Alternativa seleccionada')),  # catch-all PYF
]


def get_lineas_servicio(
    empresa: str | None,
    nombre_servicio: str | None,
    valor_total: int,
) -> list[tuple[str, int]]:
    """Devuelve [(nombre, valor_pesos), …] con el desglose del servicio.

    Busca en _BREAKDOWN_TABLE la primera entrada cuyo fragmento_empresa esté
    contenido en la empresa y cuyo fragmento_servicio esté contenido en el
    nombre del servicio (ambos en minúsculas). Ajusta el redondeo para que
    la suma sea exactamente igual a valor_total.
    """
    emp = (empresa or "").lower()
    svc = (nombre_servicio or "").lower()

    plantilla = _REC_STD  # default
    for frag_emp, frag_svc, lineas in _BREAKDOWN_TABLE:
        if frag_emp in emp and frag_svc in svc:
            plantilla = lineas
            break

    calculadas = [(nom, round(valor_total * pct)) for nom, pct in plantilla]

    # Corrección de redondeo: ajusta el ítem de mayor valor
    diff = valor_total - sum(v for _, v in calculadas)
    if diff:
        idx = max(range(len(calculadas)), key=lambda i: calculadas[i][1])
        nom, val = calculadas[idx]
        calculadas[idx] = (nom, val + diff)

    return calculadas


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

    # ── Certificate reference number (aviso o consecutivo) ───────────────────
    codigo = cert.numero_aviso or cert.numero_certificado
    if codigo:
        story.append(Paragraph(str(codigo), _cert_num))

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

        row_style = TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ])

        if cert.valor_total:
            # Desglose completo por porcentajes
            lineas = get_lineas_servicio(cert.empresa, cert.nombre_servicio, cert.valor_total)
            for nombre, valor in lineas:
                dots = "." * max(4, int((svc_col / (0.22 * cm)) - len(nombre)))
                row = Table(
                    [[Paragraph(f"{nombre.upper()}{dots}", _body),
                      Paragraph(f"$ {_formato_cop(valor)}", _svc_r)]],
                    colWidths=[svc_col, val_col],
                )
                row.setStyle(row_style)
                story.append(row)
        else:
            # Tabla simple cuando no hay valor total
            svc_name = (cert.nombre_servicio or "").upper()
            dots = "." * max(4, int((svc_col / (0.22 * cm)) - len(svc_name)))
            row = Table(
                [[Paragraph(f"{svc_name}{dots}", _body), Paragraph("-", _svc_r)]],
                colWidths=[svc_col, val_col],
            )
            row.setStyle(row_style)
            story.append(row)

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
