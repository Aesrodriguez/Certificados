"""Catálogo de empresas, tipos de documento y servicios.

Fuente: documento "Elaboración de Certificado (Descripción)".
Los valores guardados en BD para `empresa` se mantienen cortos ("RECORDAR",
"PARQUES Y FUNERARIAS") por compatibilidad con los datos existentes y con las
claves de las plantillas de servicios; la etiqueta visible es la razón social.
"""

import unicodedata

EMPRESA_PYF = "PARQUES Y FUNERARIAS"
EMPRESA_RECORDAR = "RECORDAR"

EMPRESAS: dict[str, str] = {
    EMPRESA_PYF: "PARQUES Y FUNERARIAS SAS",
    EMPRESA_RECORDAR: "RECORDAR PREVISION EXEQUIAL TOTAL SAS",
}

TIPO_FACTURA = "CERTIFICADO DE GASTOS POR FACTURA"
TIPO_SERVICIOS = "CERTIFICADO DE GASTOS POR SERVICIOS"
TIPO_ELEM_SENCILLO = "CERTIFICADO DE ELEMENTOS SENCILLO"
TIPO_ELEM_DETALLADO = "CERTIFICADO DE ELEMENTOS DETALLADO"

TIPOS_POR_EMPRESA: dict[str, list[str]] = {
    EMPRESA_PYF: [TIPO_FACTURA, TIPO_ELEM_SENCILLO, TIPO_ELEM_DETALLADO],
    EMPRESA_RECORDAR: [TIPO_SERVICIOS],
}

TIPOS_GASTOS = {TIPO_FACTURA, TIPO_SERVICIOS}

OTROS = "OTROS"

SERVICIOS_POR_EMPRESA: dict[str, list[str]] = {
    EMPRESA_PYF: [
        "SERVICIO FUNERARIO ESTILO L",
        "SERVICIO FUNERARIO ESTILO K",
        "SERVICIO FUNERARIO ESTILO J",
        "SERVICIO FUNERARIO ESTILO GRAN EXTRA",
        "CREMACION INTEGRADA",
        "SERVICIO FUNERARIO ESTILO CLASICO",
        "SERVICIO FUNERARIO ESTILO SUPERIOR",
        "SERVICIO FUNERARIO ESTILO EXCELENCIA",
        "SERVICIO FUNERARIO ESTILO EXTRA",
        OTROS,
    ],
    EMPRESA_RECORDAR: [
        "SERVICIO FUNERARIO CLASICO",
        "SERVICIO FUNERARIO SUPERIOR",
        "SERVICIO FUNERARIO EXCELENCIA",
        "SERVICIO DE CREMACION",
        "ALQUILER BUSETA",
        "LOTE EN ARRIENDO POR 4 AÑOS CON OSARIO",
        "LOTE EN ARRIENDO POR 4 AÑOS SIN OSARIO",
        "CREMACION DE CUERPO CON CENIZARIO",
        "ALQUILER BOVEDA EN OTRO CEMENTERIO",
        "DERECHOS MEMORIALES",
        "SERVICIOS DE CEMENTERIO",
        OTROS,
    ],
}

DESTINO_CREMACION = "Cremación – Destino Final"
DESTINO_INHUMACION = "Inhumación – Destino Final"


def norm(s: str | None) -> str:
    """Minúsculas y sin tildes, para comparar nombres de forma tolerante."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def es_recordar(empresa: str | None) -> bool:
    return "recordar" in norm(empresa)


def discrimina(empresa: str | None, servicio: str | None) -> bool:
    """¿El valor de este servicio se desglosa por porcentajes?

    - PARQUES Y FUNERARIAS: todos menos OTROS.
    - RECORDAR: solo servicios funerarios y el servicio de cremación.
    """
    s = norm(servicio)
    if not s or s == norm(OTROS):
        return False
    if es_recordar(empresa):
        return s.startswith("servicio funerario") or s == "servicio de cremacion"
    return True


def destino_final(servicios: list[str]) -> str | None:
    """Leyenda que va antes del total: cremación tiene prioridad sobre inhumación."""
    nombres = [norm(s) for s in servicios if s]
    if any("cremacion" in s for s in nombres):
        return DESTINO_CREMACION
    if any(s.startswith("servicio funerario") for s in nombres):
        return DESTINO_INHUMACION
    return None


def solo_digitos(s: str | None) -> str:
    return "".join(c for c in (s or "") if c.isdigit())
