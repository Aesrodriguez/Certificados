"""Test de humo del PDF: se genera sin BD y se revisa el texto que contiene."""
import asyncio
import io
import uuid
from datetime import date

import pytest
from pypdf import PdfReader

from app.models import CertificateRequest
from app.services import servicio_service
from app.services.pdf_service import build_certificate_pdf

ESTILO_L = "SERVICIO FUNERARIO ESTILO L"


@pytest.fixture(autouse=True)
def sin_plantillas_bd(monkeypatch):
    async def _vacias(db):
        return []

    monkeypatch.setattr(servicio_service, "_plantillas_activas", _vacias)


def _cert() -> CertificateRequest:
    return CertificateRequest(
        id=uuid.uuid4(),
        cliente_nombre_completo="ANA PEREZ",
        cliente_tipo_documento="CC",
        cliente_numero_documento="123456",
        fallecido_nombre_completo="JUAN PEREZ",
        fallecido_tipo_documento="CC",
        fallecido_numero_documento="654321",
        fallecido_fecha_fallecimiento=date(2026, 10, 1),
        fecha_solicitud_documento=date(2026, 10, 5),
        empresa="PARQUES Y FUNERARIAS",
        tipo_certificado="CERTIFICADO DE GASTOS POR FACTURA",
        numero_factura="F-1",
        numero_certificado="1",
        nombre_servicio=ESTILO_L,
        valor_total=1_000_000,
        servicios_json=[{"servicio": ESTILO_L, "nombre": ESTILO_L, "valor": 1_000_000}],
    )


@pytest.fixture
def texto_pdf() -> str:
    cert = _cert()
    grupos, destino = asyncio.run(servicio_service.build_desglose(None, cert))
    pdf = build_certificate_pdf(cert, signer_name="FIRMANTE", grupos=grupos, destino=destino)
    assert pdf.startswith(b"%PDF")
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf)).pages)


def test_total_aparece_una_sola_vez(texto_pdf):
    # Se quitó la fila TOTAL del inicio de la tabla; queda solo la línea final.
    assert texto_pdf.count("TOTAL:") == 1
    assert "UN MILLÓN PESOS M/L" in texto_pdf or "UN MILLON PESOS M/L" in texto_pdf


def test_producto_encabeza_el_desglose(texto_pdf):
    assert "CERTIFICAMOS" in texto_pdf
    assert ESTILO_L in texto_pdf
    assert texto_pdf.index(ESTILO_L) < texto_pdf.index("TOTAL:")
