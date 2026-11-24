"""Tests de build_desglose: los grupos de líneas y el título del producto en cada uno."""
import asyncio
from types import SimpleNamespace

import pytest

from app.services import servicio_service
from app.services.servicio_service import build_desglose

PYF = "PARQUES Y FUNERARIAS"
RECORDAR = "RECORDAR"
ESTILO_L = "SERVICIO FUNERARIO ESTILO L"


@pytest.fixture(autouse=True)
def sin_plantillas_bd(monkeypatch):
    """Sin plantillas en BD: se usan las fijas del código (get_lineas_servicio)."""

    async def _vacias(db):
        return []

    monkeypatch.setattr(servicio_service, "_plantillas_activas", _vacias)


def _cert(**kwargs):
    base = {"empresa": PYF, "nombre_servicio": None, "valor_total": None, "servicios_json": None}
    return SimpleNamespace(**{**base, **kwargs})


def _desglose(cert):
    return asyncio.run(build_desglose(None, cert))


def test_formato_nuevo_con_un_servicio_lleva_titulo():
    # Antes, con un único ítem el título se borraba; ahora encabeza el desglose.
    cert = _cert(servicios_json=[{"servicio": ESTILO_L, "nombre": ESTILO_L, "valor": 1_000_000}])
    grupos, destino = _desglose(cert)

    assert len(grupos) == 1
    g = grupos[0]
    assert g["titulo"] == ESTILO_L
    assert g["valor"] == 1_000_000
    assert len(g["lineas"]) > 1
    assert sum(v for _, v in g["lineas"]) == 1_000_000
    assert destino == "Inhumación – Destino Final"


def test_formato_nuevo_con_varios_servicios():
    cert = _cert(
        servicios_json=[
            {"servicio": ESTILO_L, "nombre": ESTILO_L, "valor": 1_000_000},
            {"servicio": "CREMACION INTEGRADA", "nombre": "CREMACION INTEGRADA", "valor": 500_000},
        ]
    )
    grupos, destino = _desglose(cert)

    assert [g["titulo"] for g in grupos] == [ESTILO_L, "CREMACION INTEGRADA"]
    for g in grupos:
        assert sum(v for _, v in g["lineas"]) == g["valor"]
    assert destino == "Cremación – Destino Final"  # cremación tiene prioridad


def test_servicio_que_no_se_desglosa_no_repite_titulo():
    # OTROS no se desglosa: queda una sola línea con su nombre y sin título repetido.
    cert = _cert(servicios_json=[{"servicio": "OTROS", "nombre": "TRASLADO", "valor": 200_000}])
    grupos, destino = _desglose(cert)

    assert grupos == [{"titulo": None, "valor": 200_000, "lineas": [("TRASLADO", 200_000)]}]
    assert destino is None


def test_recordar_alquiler_no_se_desglosa():
    cert = _cert(
        empresa=RECORDAR,
        servicios_json=[{"servicio": "ALQUILER BUSETA", "nombre": "ALQUILER BUSETA", "valor": 90_000}],
    )
    grupos, _ = _desglose(cert)

    assert grupos == [{"titulo": None, "valor": 90_000, "lineas": [("ALQUILER BUSETA", 90_000)]}]


def test_formato_antiguo_toma_nombre_servicio_como_titulo():
    cert = _cert(
        nombre_servicio=ESTILO_L,
        servicios_json=[{"nombre": "Cofre", "valor": 600_000}, {"nombre": "Sala", "valor": 400_000}],
    )
    grupos, _ = _desglose(cert)

    assert grupos == [
        {"titulo": ESTILO_L, "valor": 1_000_000, "lineas": [("Cofre", 600_000), ("Sala", 400_000)]}
    ]


def test_formato_antiguo_una_linea_sin_titulo():
    cert = _cert(nombre_servicio=ESTILO_L, servicios_json=[{"nombre": "Cofre", "valor": 600_000}])
    grupos, _ = _desglose(cert)

    assert grupos[0]["titulo"] is None


def test_solo_valor_total_se_desglosa_con_plantilla_y_titulo():
    cert = _cert(nombre_servicio=ESTILO_L, valor_total=2_000_000)
    grupos, destino = _desglose(cert)

    assert len(grupos) == 1
    assert grupos[0]["titulo"] == ESTILO_L
    assert sum(v for _, v in grupos[0]["lineas"]) == 2_000_000
    assert destino == "Inhumación – Destino Final"


def test_sin_servicios_ni_valor():
    grupos, destino = _desglose(_cert(nombre_servicio=ESTILO_L))
    assert grupos == []
    assert destino == "Inhumación – Destino Final"
