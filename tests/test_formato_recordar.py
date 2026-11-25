"""Certificado de gastos por servicio (RECORDAR) según el modelo de Clara (novedades 7, 9, 10, 12)
y sello de cancelado configurable por tipo (novedad 5)."""
import asyncio
import io
import uuid
from datetime import date

import pytest
from pypdf import PdfReader

from app.core.catalogo import TIPO_FACTURA, TIPO_SERVICIOS
from app.models import CertificateRequest
from app.services import formato_recordar, servicio_service
from app.services.appsetting_service import FormatoCertificado
from app.services.formato_recordar import Fila
from app.services.pdf_service import build_certificate_pdf, lleva_sello_cancelado


@pytest.fixture(autouse=True)
def sin_plantillas_bd(monkeypatch):
    async def _vacias(db):
        return []

    monkeypatch.setattr(servicio_service, "_plantillas_activas", _vacias)


def _cert_recordar(**kw) -> CertificateRequest:
    datos = dict(
        id=uuid.uuid4(),
        empresa="RECORDAR",
        tipo_certificado=TIPO_SERVICIOS,
        numero_certificado="23449",
        cliente_nombre_completo="EGLIS DEYANIRA RIVERO ANDRADE",
        cliente_tipo_documento="CE",
        cliente_numero_documento="1069507",
        fallecido_nombre_completo="ALVARO JULIO DE LA PUENTE MEJIA",
        fallecido_tipo_documento="CC",
        fallecido_numero_documento="72.126.103",
        fecha_servicio=date(2026, 9, 29),
        fecha_afiliacion=date(2024, 11, 29),
        fecha_solicitud_documento=date(2026, 10, 23),
        nombre_servicio="SERVICIO FUNERARIO CLASICO",
        valor_total=6_419_968,
        servicios_json=[
            {"servicio": "SERVICIO FUNERARIO CLASICO", "nombre": "SERVICIO FUNERARIO CLASICO",
             "valor": 3_270_000},
            {"servicio": "ALQUILER BUSETA", "nombre": "ALQUILER BUSETA", "valor": 208_968},
            {"servicio": "CREMACION DE CUERPO CON CENIZARIO",
             "nombre": "CREMACION DE CUERPO CON CENIZARIO", "valor": 2_941_000},
        ],
    )
    datos.update(kw)
    return CertificateRequest(**datos)


def _texto_pdf(cert, formato=None) -> str:
    grupos, destino = asyncio.run(servicio_service.build_desglose(None, cert))
    pdf = build_certificate_pdf(cert, signer_name="CLARA LLANOS MAURY", grupos=grupos,
                                destino=destino, formato=formato)
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


# ── Encabezado (novedad 7) ──────────────────────────────────────────────────

def test_encabezado_como_el_modelo():
    renglones = formato_recordar.encabezado(_cert_recordar(), "Barranquilla")
    assert renglones == [
        [("Sede:", "Barranquilla"), ("Fecha de Servicio:", "29 de septiembre 2026"),
         ("Tipo de servicio:", "Clásica")],
        [("Titular Beneficiario:", "EGLIS DEYANIRA RIVERO ANDRADE C.E. N° 1069507")],
        [("Fallecido:", "ALVARO JULIO DE LA PUENTE MEJIA C.C. N° 72.126.103 (Q.E.P.D)")],
        [("Fecha de Afiliación:", "29/11/2024")],
    ]


def test_encabezado_omite_datos_vacios():
    cert = _cert_recordar(fecha_servicio=None, fecha_afiliacion=None)
    renglones = formato_recordar.encabezado(cert, "Barranquilla")
    assert renglones[0] == [("Sede:", "Barranquilla"), ("Tipo de servicio:", "Clásica")]
    assert all(k != "Fecha de Afiliación:" for r in renglones for k, _ in r)


@pytest.mark.parametrize("servicio, tipo", [
    ("SERVICIO FUNERARIO SUPERIOR", "Superior"),
    ("SERVICIO FUNERARIO EXCELENCIA", "Excelencia"),
    ("SERVICIO DE CREMACION", "Cremación"),
    ("ALQUILER BUSETA", None),
])
def test_tipo_de_servicio(servicio, tipo):
    cert = _cert_recordar(nombre_servicio=servicio,
                          servicios_json=[{"servicio": servicio, "nombre": servicio, "valor": 1}])
    assert formato_recordar.tipo_servicio(cert) == tipo


# ── Descripción del servicio (novedades 9 y 10) ─────────────────────────────

def test_otros_servicios_van_aparte_y_en_negrita():
    cert = _cert_recordar()
    grupos, _ = asyncio.run(servicio_service.build_desglose(None, cert))
    filas = formato_recordar.filas(grupos)

    assert filas[0] == Fila("titulo", "SERVICIO FUNERARIO CLASICO", 3_270_000)
    tipos = [f.tipo for f in filas]
    i = tipos.index("espacio")
    assert set(tipos[1:i]) == {"linea"}  # el desglose del funerario
    assert filas[i + 1:] == [
        Fila("extra", "ALQUILER BUSETA", 208_968),
        Fila("extra", "CREMACION DE CUERPO CON CENIZARIO", 2_941_000),
    ]


# ── Bloque del titular (novedad 12) ─────────────────────────────────────────

def test_bloque_titular():
    assert formato_recordar.bloque_titular(_cert_recordar()) == [
        ("TITULAR:", "EGLIS DEYANIRA RIVERO ANDRADE C.E. N° 1069507"),
        ("BENEFICIARIO:", "ALVARO JULIO DE LA PUENTE MEJIA C.C. N° 72.126.103 (Q.E.P.D)"),
        ("PFG Por:", "$ 6.419.968"),
    ]


# ── PDF completo ────────────────────────────────────────────────────────────

def test_pdf_recordar_sigue_el_modelo():
    texto = _texto_pdf(_cert_recordar())

    assert "CERTIFICACIÓN DE GASTOS" in texto
    assert "CERTIFICAMOS" not in texto
    assert "Sede: Barranquilla" in texto
    assert "DESCRIPCIÓN DEL SERVICIO" in texto
    assert "Servicio: Clásica" in texto
    assert "SERVICIOS UTILIZADOS" not in texto
    assert "Son: SEIS MILLONES" in texto
    assert "TOTAL:" not in texto
    assert "PFG Por: $ 6.419.968" in texto
    # Orden del modelo: desglose, otros servicios, destino, Son:, bloque titular.
    orden = ["SERVICIO FUNERARIO CLASICO", "ALQUILER BUSETA", "CREMACION DE CUERPO",
             "Destino Final", "Son:", "TITULAR:", "BENEFICIARIO:", "PFG Por:"]
    posiciones = [texto.index(t) for t in orden]
    assert posiciones == sorted(posiciones)


def test_pdf_parques_y_funerarias_no_cambia():
    cert = _cert_recordar(empresa="PARQUES Y FUNERARIAS", tipo_certificado=TIPO_FACTURA,
                          numero_factura="F-1")
    texto = _texto_pdf(cert)
    assert "CERTIFICAMOS" in texto
    assert "SERVICIOS UTILIZADOS" in texto
    assert "TOTAL:" in texto
    assert "CERTIFICACIÓN DE GASTOS" not in texto
    assert "PFG Por" not in texto


def test_sede_configurable_en_el_pdf():
    texto = _texto_pdf(_cert_recordar(), FormatoCertificado(sede="Soledad"))
    assert "Sede: Soledad" in texto


# ── Sello configurable (novedad 5) ──────────────────────────────────────────

def test_sello_por_defecto_solo_gastos_por_servicio():
    assert lleva_sello_cancelado(_cert_recordar())
    assert not lleva_sello_cancelado(_cert_recordar(empresa="PARQUES Y FUNERARIAS",
                                                    tipo_certificado=TIPO_FACTURA))


def test_sello_se_activa_para_factura_desde_configuracion():
    factura = _cert_recordar(empresa="PARQUES Y FUNERARIAS", tipo_certificado=TIPO_FACTURA)
    assert lleva_sello_cancelado(factura, frozenset({TIPO_FACTURA, TIPO_SERVICIOS}))
    assert not lleva_sello_cancelado(_cert_recordar(), frozenset({TIPO_FACTURA}))


def test_solicitud_antigua_sin_tipo_se_deduce_de_la_empresa():
    assert lleva_sello_cancelado(_cert_recordar(tipo_certificado=None))
    assert not lleva_sello_cancelado(
        _cert_recordar(empresa="PARQUES Y FUNERARIAS", tipo_certificado=None)
    )


# ── Sello sin fecha y fecha en letras debajo (novedades 11 y 13) ────────────

def _aprobado_el(d: date, **kw):
    from datetime import datetime, timezone
    return _cert_recordar(reviewed_at=datetime(d.year, d.month, d.day, 17, tzinfo=timezone.utc), **kw)


def test_fecha_sello_en_letras():
    from app.services.pdf_service import fecha_sello

    assert fecha_sello(_aprobado_el(date(2026, 10, 30)), "Barranquilla") == \
        "Barranquilla, octubre 30 de 2026"
    assert fecha_sello(_aprobado_el(date(2026, 9, 3)), "Soledad") == "Soledad, septiembre 3 de 2026"


def test_pdf_lleva_fecha_en_letras_bajo_el_sello_y_no_dd_mm_aaaa():
    texto = _texto_pdf(_aprobado_el(date(2026, 11, 23)))
    assert "Barranquilla, noviembre 23 de 2026" in texto
    assert "23/11/2026" not in texto  # antes salía debajo del sello
    assert "23/10/2026" in texto  # la fecha de solicitud debajo de la firma no cambia


def test_sin_sello_no_hay_fecha_en_letras():
    cert = _aprobado_el(date(2026, 11, 23), empresa="PARQUES Y FUNERARIAS",
                        tipo_certificado=TIPO_FACTURA)
    assert "Barranquilla, noviembre 23 de 2026" not in _texto_pdf(cert)
