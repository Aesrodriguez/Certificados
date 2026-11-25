"""Contenido del certificado de gastos por servicio (RECORDAR), según el modelo de Clara.

Solo arma los datos (textos y filas). El PDF (pdf_service) y la vista previa
(preview.html) los dibujan, así los dos dicen siempre lo mismo.

Estructura del modelo:
  BQ-GER-…                                   (código)
  CERTIFICACIÓN DE GASTOS                    (encabezado)
  Sede: … Fecha de Servicio: … Tipo de servicio: …
  Titular Beneficiario: … / Fallecido: … (Q.E.P.D) / Fecha de Afiliación: …
  DESCRIPCIÓN DEL SERVICIO
  Servicio: Clásica
  SERVICIO FUNERARIO …                $ total     (negrita) y debajo su desglose
                                                  (espacio)
  ALQUILER BUSETA …                   $ valor     (negrita, aparte)
  CREMACION DE CUERPO CON CENIZARIO   $ valor     (negrita, aparte)
  (Cremación – Destino Final)
  Son: … PESOS M/L ($ …)
  TITULAR: … / BENEFICIARIO: … (Q.E.P.D) / PFG Por: $ …   (antes de las firmas)
"""

from dataclasses import dataclass
from datetime import date

from app.core.catalogo import norm

_MESES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

_ABREV_DOC = {"CC": "C.C.", "CE": "C.E.", "TI": "T.I.", "RC": "R.C.", "PA": "Pasaporte"}

# "SERVICIO FUNERARIO CLASICO" → "Clásica", como en el modelo.
_ESTILOS = {"clasico": "Clásica", "superior": "Superior", "excelencia": "Excelencia"}


@dataclass(frozen=True)
class Fila:
    tipo: str  # "titulo" (negrita), "linea" (desglose), "extra" (negrita, aparte), "espacio"
    nombre: str = ""
    valor: int | None = None


def documento(tipo: str | None, numero: str | None) -> str:
    """'C.C. N° 72.126.103' a partir del tipo y número guardados."""
    numero = (numero or "").strip()
    if not numero:
        return ""
    abrev = _ABREV_DOC.get((tipo or "").strip().upper(), (tipo or "").strip())
    return f"{abrev} N° {numero}".strip()


def fecha_servicio_texto(d: date) -> str:
    """'29 de septiembre 2026', como en el modelo."""
    return f"{d.day} de {_MESES[d.month]} {d.year}"


def _servicios(cert) -> list[str]:
    items = [i for i in (cert.servicios_json or []) if isinstance(i, dict) and i.get("servicio")]
    nombres = [str(i["servicio"]) for i in items]
    return nombres or ([cert.nombre_servicio] if cert.nombre_servicio else [])


def tipo_servicio(cert) -> str | None:
    """Tipo de servicio del encabezado: el estilo del servicio funerario o 'Cremación'."""
    for nombre in _servicios(cert):
        n = norm(nombre)
        if n.startswith("servicio funerario"):
            estilo = n.removeprefix("servicio funerario").strip()
            return _ESTILOS.get(estilo, estilo.capitalize() or None)
    for nombre in _servicios(cert):
        if "cremacion" in norm(nombre):
            return "Cremación"
    return None


def encabezado(cert, sede: str) -> list[list[tuple[str, str]]]:
    """Renglones del encabezado como pares (etiqueta, valor); se omiten los vacíos."""
    fal_doc = documento(cert.fallecido_tipo_documento, cert.fallecido_numero_documento)
    tit_doc = documento(cert.cliente_tipo_documento, cert.cliente_numero_documento)
    titular = cert.cliente_nombre_completo or cert.fallecido_nombre_completo or ""
    if not cert.cliente_nombre_completo:
        tit_doc = fal_doc

    renglones = [
        [
            ("Sede:", sede),
            ("Fecha de Servicio:",
             fecha_servicio_texto(cert.fecha_servicio) if cert.fecha_servicio else ""),
            ("Tipo de servicio:", tipo_servicio(cert) or ""),
        ],
        [("Titular Beneficiario:", f"{titular} {tit_doc}".strip())],
        [("Fallecido:", f"{cert.fallecido_nombre_completo or ''} {fal_doc} (Q.E.P.D)".strip())],
        [("Fecha de Afiliación:",
          cert.fecha_afiliacion.strftime("%d/%m/%Y") if cert.fecha_afiliacion else "")],
    ]
    return [r for r in ([(k, v) for k, v in fila if v] for fila in renglones) if r]


def filas(grupos: list[dict]) -> list[Fila]:
    """Filas de la descripción del servicio.

    Los servicios con desglose (funerario, cremación) van con su título en negrita y
    sus componentes. Los demás (alquiler de buseta, cremación con cenizario…) van
    aparte y en negrita, separados del desglose por un espacio.
    """
    resultado: list[Fila] = []
    for g in grupos:
        con_desglose = bool(g.get("titulo")) or len(g["lineas"]) > 1
        if con_desglose:
            if g.get("titulo"):
                resultado.append(Fila("titulo", g["titulo"], g["valor"]))
            resultado.extend(Fila("linea", n, v) for n, v in g["lineas"])
        else:
            if resultado and resultado[-1].tipo != "extra":
                resultado.append(Fila("espacio"))
            nombre, valor = g["lineas"][0]
            resultado.append(Fila("extra", nombre, valor))
    return resultado


def bloque_titular(cert) -> list[tuple[str, str]]:
    """Bloque que va antes de las firmas: TITULAR, BENEFICIARIO y PFG Por."""
    fal_doc = documento(cert.fallecido_tipo_documento, cert.fallecido_numero_documento)
    tit_doc = documento(cert.cliente_tipo_documento, cert.cliente_numero_documento)
    titular = f"{cert.cliente_nombre_completo or ''} {tit_doc}".strip()
    if not cert.cliente_nombre_completo:
        titular = f"{cert.fallecido_nombre_completo or ''} {fal_doc}".strip()
    bloque = [
        ("TITULAR:", titular),
        ("BENEFICIARIO:", f"{cert.fallecido_nombre_completo or ''} {fal_doc} (Q.E.P.D)".strip()),
    ]
    if cert.valor_total:
        bloque.append(("PFG Por:", f"$ {cert.valor_total:,}".replace(",", ".")))
    return [(k, v) for k, v in bloque if v]
