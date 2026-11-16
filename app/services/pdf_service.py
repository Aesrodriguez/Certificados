import html
import io
from datetime import date, datetime, timedelta, timezone
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

from app.core.catalogo import TIPO_SERVICIOS, es_recordar as _es_recordar, norm, solo_digitos
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
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo", 0.00),
    ("(Carroza Funebre)", 0.03),
    ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
    ("Cafeteria (Bebidas calientes en sala)", 0.05),
    ("Carteles Virtuales", 0.01),
    ("Trámites ante autoridades competentes", 0.00),
    ("(Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
    ("Velación por 24 horas", 0.31),
]

_REC_CREMACION = [  # RECORDAR — Servicio de cremación (base: cremación PYF, editable en Servicios)
    ("Traslado del cuerpo dentro del perímetro urbano", 0.04),
    ("Preparación normal del cuerpo", 0.09),
    ("Suministro del féretro según la Alternativa seleccionada", 0.41),
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo", 0.00),
    ("(Carroza Funebre)", 0.03),
    ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
    ("Cafeteria (Bebidas calientes en sala)", 0.05),
    ("Carteles Virtuales", 0.01),
    ("Trámites ante autoridades competentes", 0.00),
    ("(Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
    ("Velación por 24 horas", 0.21),
    ("Reducción del cuerpo a Cenizas por medio del calor", 0.10),
]

_REC_TRANSP = [  # RECORDAR — Solo transporte, velación y restos
    ("Traslado terrestre de la persona fallecida al parque cementerio Jardines de Eternidad sede norte", 0.30),
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo", 0.00),
    ("(Carroza Funebre)", 0.22),
    ("Cafeteria (Bebidas calientes en sala)", 0.05),
    ("Carteles Virtuales", 0.01),
    ("Velación por 24 horas", 0.42),
]

_REC_TRANSP_MISA = [  # RECORDAR — Solo transporte, velación, misa y restos
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo", 0.00),
    ("(Carroza Funebre)", 0.50),
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
        ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo", 0.00),
        ("(Carroza Funebre)", 0.03),
        ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
        ("Cafeteria (Bebidas calientes en sala)", 0.05),
        ("Carteles Virtuales", 0.01),
        ("Trámites ante autoridades competentes", 0.00),
        ("(Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
        ("Velación normal (24 horas)", 0.31),
        ("Asesoria las 24 horas", 0.00),
    ]

_PYF_CREMACION = [  # PYF — Cremación integrada
    ("Recogida del cuerpo dentro del perímetro urbano", 0.04),
    ("Preparación normal del cuerpo", 0.09),
    ('Cofre funebre "L" o el equivalente a talla y peso de fallecido', 0.41),
    ("Traslado urbano de la persona fallecida a la sala de velación y Campo Santo", 0.00),
    ("(Carroza Funebre)", 0.03),
    ("Celebración religiosa (si el cliente lo desea)-(Tramites eclesiasticos)", 0.02),
    ("Cafeteria (Bebidas calientes en sala)", 0.05),
    ("Carteles Virtuales", 0.01),
    ("Trámites ante autoridades competentes", 0.00),
    ("(Licencia de inhumación o cremación- Registro de Defunción)", 0.04),
    ("Velación normal (24 horas)", 0.21),
    ("Reducción del cuerpo a Cenizas por medio del calor", 0.10),
    ("Asesoria las 24 horas", 0.00),
]

# Tabla de búsqueda: (fragmento_empresa, fragmento_servicio) → desglose
# La empresa y el nombre de servicio se comparan en minúsculas (in).
_BREAKDOWN_TABLE: list[tuple[str, str, list]] = [
    # RECORDAR
    ("recordar", "cremacion",                _REC_CREMACION),
    ("recordar", "transporte velacion misa", _REC_TRANSP_MISA),
    ("recordar", "transporte velacion",      _REC_TRANSP),
    ("recordar", "",                          _REC_STD),   # catch-all RECORDAR
    # PARQUES Y FUNERARIAS
    ("parques",  "cremacion",    _PYF_CREMACION),
    ("parques",  "gran extra",   _pyf_std('Cofre funebre "Gran Extra" o el equivalente a talla y peso de fallecido')),
    ("parques",  "estilo j",     _pyf_std('Cofre funebre "J" o el equivalente a talla y peso de fallecido')),
    ("parques",  "estilo k",     _pyf_std('Cofre funebre "K" o el equivalente a talla y peso de fallecido')),
    ("parques",  "estilo l",     _pyf_std('Cofre funebre "L" o el equivalente a talla y peso de fallecido')),
    ("parques",  "estilo clasico",    _pyf_std('Cofre funebre "Clásico" o el equivalente a talla y peso de fallecido')),
    ("parques",  "estilo superior",   _pyf_std('Cofre funebre "Superior" o el equivalente a talla y peso de fallecido')),
    ("parques",  "estilo excelencia", _pyf_std('Cofre funebre "Excelencia" o el equivalente a talla y peso de fallecido')),
    ("parques",  "estilo extra",      _pyf_std('Cofre funebre "Extra" o el equivalente a talla y peso de fallecido')),
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
    emp = norm(empresa)
    svc = norm(nombre_servicio)

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


def encrypt_pdf(pdf_bytes: bytes, password: str) -> bytes:
    """Encrypt PDF with the given user password using pypdf."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password, owner_password=None)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _draw_letterhead(canvas, doc):
    """Draw the GRUPO RECORDAR letterhead as full-page background on every page."""
    canvas.saveState()
    canvas.drawImage(_LETTERHEAD, 0, 0, width=_PAGE_W, height=_PAGE_H,
                     preserveAspectRatio=False)
    canvas.restoreState()


_TZ = timezone(timedelta(hours=-5), "America/Bogota")  # Colombia no usa horario de verano
_SELLO_COLOR = colors.HexColor("#b91c1c")

_sello = ParagraphStyle("Sello", parent=_styles["Normal"], fontSize=14, leading=16,
                        fontName="Helvetica-Bold", textColor=_SELLO_COLOR, alignment=1)
_sello_fecha = ParagraphStyle("SelloFecha", parent=_styles["Normal"], fontSize=9,
                              textColor=_SELLO_COLOR, alignment=1, spaceBefore=3)


def fecha_elaboracion(cert: CertificateRequest) -> date:
    """Día en que se elabora el certificado: el de aprobación (hora Colombia) o hoy."""
    if cert.reviewed_at:
        return cert.reviewed_at.astimezone(_TZ).date()
    return datetime.now(_TZ).date()


def fecha_firma(cert: CertificateRequest) -> str:
    """Fecha que va debajo del cargo del firmante: la fecha de solicitud del documento."""
    if cert.fecha_solicitud_documento:
        return cert.fecha_solicitud_documento.strftime("%d/%m/%Y")
    if cert.created_at:
        return cert.created_at.astimezone(_TZ).strftime("%d/%m/%Y")
    return fecha_elaboracion(cert).strftime("%d/%m/%Y")


def lleva_sello_cancelado(cert: CertificateRequest) -> bool:
    return cert.tipo_certificado == TIPO_SERVICIOS or _es_recordar(cert.empresa)


def cuerpo_html(cert: CertificateRequest) -> str:
    """Párrafo principal del certificado (marcado simple <b>, valores escapados).

    Lo usan tanto el PDF como la vista previa, para que siempre digan lo mismo.
    """
    e = html.escape
    tit_nom = e(cert.cliente_nombre_completo or "")
    tit_doc = e(cert.cliente_numero_documento or "")
    fal_nom = e(cert.fallecido_nombre_completo or "")
    fal_doc = e(cert.fallecido_numero_documento or "")

    fechas = []
    if cert.fecha_servicio:
        fechas.append(f"Fecha del servicio el día {_fecha_larga(cert.fecha_servicio)}.")
    if cert.fallecido_fecha_fallecimiento:
        fechas.append(f"Fecha de Defunción el día {_fecha_larga(cert.fallecido_fecha_fallecimiento)}.")
    cierre = " ".join(fechas)

    afiliacion = (
        f", afiliado (a) desde el día {_fecha_larga(cert.fecha_afiliacion)}"
        if cert.fecha_afiliacion else ""
    )

    if _es_recordar(cert.empresa):
        mismo = solo_digitos(cert.cliente_numero_documento) == solo_digitos(cert.fallecido_numero_documento)
        if mismo or not tit_nom:
            # El fallecido era el titular del plan — no repetirlo como beneficiario
            return (
                f"Que el (la) señor (a) <b>{fal_nom}</b>, identificado (a) con la cédula de "
                f"ciudadanía N° {fal_doc} (Q.E.P.D){afiliacion}; era titular de los servicios que "
                f"adquirió en nuestra empresa que se relacionan a continuación. {cierre}"
            ).strip()
        return (
            f"Que el (la) señor (a) <b>{tit_nom}</b>, identificado (a) con la cédula de "
            f"ciudadanía N° {tit_doc}{afiliacion}; titular de los servicios que adquirió en "
            f"nuestra empresa que se relacionan a continuación. Los cuales fueron utilizados con "
            f"el beneficiario (a) <b>{fal_nom}</b> identificado(a) con la cédula de ciudadanía "
            f"N° {fal_doc} (Q.E.P.D); {cierre}"
        ).strip()

    return (
        f"Que el (la) señor (a) <b>{tit_nom}</b>, identificado (a) con la cédula de ciudadanía "
        f"N° {tit_doc}; titular de los servicios que adquirió en nuestra empresa que se relaciona "
        f"a continuación. Los cuales fueron utilizados con el beneficiario (a) <b>{fal_nom}</b> "
        f"identificado(a) con la cédula de ciudadanía N° {fal_doc} (Q.E.P.D); {cierre}"
    ).strip()


def pdf_password(cert: CertificateRequest) -> str:
    """Contraseña del PDF: cédula del fallecido sin puntos, comas ni otros caracteres."""
    return solo_digitos(cert.fallecido_numero_documento)


def build_certificate_pdf(
    cert: CertificateRequest,
    signer_name: str = "",
    signer_cargo: str = "Administrador de Ciudad",
    grupos: list[dict] | None = None,
    destino: str | None = None,
) -> bytes:
    buffer = io.BytesIO()

    issue = fecha_elaboracion(cert)

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
    content_width = _PAGE_W - _LEFT_MARGIN - _RIGHT_MARGIN

    # ── Certificate reference number ──────────────────────────────────────────
    if cert.numero_aviso:
        codigo = f"BQ-GER-5-1-{cert.numero_aviso}-{issue.year}"
    elif cert.numero_certificado:
        codigo = cert.numero_certificado
    else:
        codigo = None
    if codigo:
        story.append(Paragraph(html.escape(codigo), _cert_num))

    # ── CERTIFICAMOS heading ──────────────────────────────────────────────────
    story.append(Paragraph("CERTIFICAMOS", _heading))

    # ── Body paragraph ────────────────────────────────────────────────────────
    es_recordar = _es_recordar(cert.empresa)
    story.append(Paragraph(cuerpo_html(cert), _body))
    story.append(Spacer(1, 0.3 * cm))

    # ── Services table ────────────────────────────────────────────────────────
    grupos = grupos or []
    if grupos or cert.nombre_servicio or cert.valor_total:
        val_col = 4 * cm
        svc_col = content_width - val_col

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

        def _row(nombre: str, valor: int | None, style=_body, bold_val=True):
            dots = "." * max(4, int((svc_col / (0.22 * cm)) - len(nombre)))
            if valor is None:
                val_str = "-"
            else:
                val_str = "$ -" if valor == 0 else f"$ {_formato_cop(valor)}"
            t = Table(
                [[Paragraph(f"{html.escape(nombre)}{dots}", style),
                  Paragraph(val_str, _svc_r)]],
                colWidths=[svc_col, val_col],
            )
            t.setStyle(row_style)
            return t

        if cert.valor_total:
            palabras_top = _numero_a_palabras(cert.valor_total)
            total_top = Table(
                [[Paragraph(f"TOTAL: {palabras_top} PESOS M/L", _svc_bold),
                  Paragraph(f"$ {_formato_cop(cert.valor_total)}", _svc_r)]],
                colWidths=[svc_col, val_col],
            )
            total_top.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (-1, 0), 0.3, colors.HexColor("#aaaaaa")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(total_top)

        if grupos:
            for g in grupos:
                if g.get("titulo"):
                    story.append(_row(g["titulo"], g["valor"], style=_svc_bold))
                for nombre, valor in g["lineas"]:
                    story.append(_row(nombre, valor))
        else:
            story.append(_row(cert.nombre_servicio or "", cert.valor_total))

        if cert.descripcion_servicio:
            story.append(Paragraph(f"({html.escape(cert.descripcion_servicio)})", _body))

        closing = Table([[""]], colWidths=[content_width])
        closing.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(closing)
        story.append(Spacer(1, 0.3 * cm))

        if destino:
            story.append(Paragraph(f"({destino})", _total))

        if cert.valor_total:
            palabras = _numero_a_palabras(cert.valor_total)
            story.append(Paragraph(
                f"TOTAL: {palabras} PESOS M/L (${_formato_cop(cert.valor_total)})",
                _total,
            ))

    # ── IVA exclusion (solo PARQUES Y FUNERARIAS — RECORDAR emite certificación, no factura) ──
    if not es_recordar:
        story.append(Paragraph(
            "Producto Excluido de IVA: Conforme con lo dispuesto por el Artículo 476, numeral 14 "
            "del estatuto tributario, se encuentran excluidos del impuesto sobre las ventas los "
            "Servicios Funerarios, los de Cremación, Inhumación y Exhumación de Cadáveres, Alquiler "
            "y Mantenimiento de Tumbas y Mausoleos.",
            _iva,
        ))

    # ── Issue paragraph ───────────────────────────────────────────────────────
    footer_text = (
        f"Se expide la presente certificación a solicitud del interesado a los "
        f"{issue.day} días del mes de {_MESES[issue.month]} de {issue.year}."
    )
    if cert.numero_factura:
        footer_text += f" Amparado bajo la Factura N° {html.escape(cert.numero_factura)}"
    elif cert.numero_recibo_caja:
        footer_text += f" Recibo de caja N° {html.escape(cert.numero_recibo_caja)}"
    story.append(Paragraph(footer_text, _footer_p))

    # ── Signature block (+ sello de cancelado para RECORDAR) ─────────────────
    story.append(Spacer(1, 1.0 * cm))
    firma: list = []
    if Path(_SIGNATURE).exists():
        sig_img = Image(_SIGNATURE, width=5 * cm, height=2 * cm)
        sig_img.hAlign = "LEFT"
        firma.append(sig_img)
    else:
        firma.append(Spacer(1, 2 * cm))
    firma.append(Paragraph(html.escape(signer_name or "Administrador de Ciudad"), _sig_name))
    firma.append(Paragraph(html.escape(signer_cargo or "Administrador de Ciudad"), _sig_role))
    firma.append(Paragraph(fecha_firma(cert), _sig_role))

    if lleva_sello_cancelado(cert):
        caja = Table([[Paragraph("CANCELADO", _sello)]], colWidths=[4.6 * cm])
        caja.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1.5, _SELLO_COLOR),
            ("ROUNDEDCORNERS", [6, 6, 6, 6]),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        sello = [Spacer(1, 0.6 * cm), caja,
                 Paragraph(issue.strftime("%d/%m/%Y"), _sello_fecha)]
        bloque = Table([[firma, sello]], colWidths=[content_width - 6 * cm, 6 * cm])
        bloque.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(bloque)
    else:
        story.extend(firma)

    doc.build(story)
    return buffer.getvalue()
