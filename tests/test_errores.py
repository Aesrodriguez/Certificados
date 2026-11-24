"""Pantallas de error: HTML para el navegador, JSON para fetch, redirecciones intactas."""
import re

import pytest
from fastapi import APIRouter, HTTPException, Query
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.errors import CSRF_INVALIDO
from app.main import app

HTML = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
JSON = {"Accept": "application/json"}

_prueba = APIRouter(prefix="/__prueba_errores__")


@_prueba.get("/inesperado")
async def _inesperado():
    raise RuntimeError("boom")


@_prueba.get("/bd")
async def _bd():
    raise OperationalError("SELECT 1", {}, ConnectionRefusedError("sin conexión"))


@_prueba.get("/integridad")
async def _integridad():
    raise IntegrityError("INSERT", {}, Exception("duplicado"))


@_prueba.get("/csrf")
async def _csrf():
    raise HTTPException(status_code=403, detail=CSRF_INVALIDO)


@_prueba.get("/negocio")
async def _negocio():
    raise HTTPException(status_code=403, detail="El certificado ya fue aprobado.")


@_prueba.get("/validacion")
async def _validacion(n: int = Query(...)):
    return {"n": n}


app.include_router(_prueba)


@pytest.fixture(scope="module")
def client():
    return TestClient(app, raise_server_exceptions=False)


def _es_pantalla(r, codigo: int, titulo: str):
    assert r.status_code == codigo
    assert r.headers["content-type"].startswith("text/html")
    assert titulo in r.text
    assert f"Error {codigo}" in r.text
    assert "Ir al inicio" in r.text
    assert r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"


def test_404_en_navegador(client):
    r = client.get("/no-existe", headers=HTML)
    _es_pantalla(r, 404, "Página no encontrada")
    assert "Volver" in r.text


def test_404_en_fetch_sigue_siendo_json(client):
    r = client.get("/no-existe", headers=JSON)
    assert r.status_code == 404
    assert r.json() == {"detail": "Not Found"}


def test_405(client):
    r = client.delete("/login", headers=HTML)
    _es_pantalla(r, 405, "Acción no permitida")


def test_redireccion_al_login_no_cambia(client):
    r = client.get("/certificates", headers=HTML, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_422_en_navegador_y_json(client):
    _es_pantalla(
        client.get("/__prueba_errores__/validacion", headers=HTML), 422, "Faltan datos"
    )
    r = client.get("/__prueba_errores__/validacion", headers=JSON)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["query", "n"]


def test_403_csrf_muestra_pagina_caducada(client):
    r = client.get("/__prueba_errores__/csrf", headers=HTML)
    _es_pantalla(r, 403, "La página caducó")
    assert CSRF_INVALIDO not in r.text


def test_403_muestra_el_motivo_de_negocio(client):
    r = client.get("/__prueba_errores__/negocio", headers=HTML)
    _es_pantalla(r, 403, "No tienes permiso")
    assert "El certificado ya fue aprobado." in r.text


def test_500_con_referencia_y_reintentar(client, caplog):
    r = client.get("/__prueba_errores__/inesperado", headers=HTML)
    _es_pantalla(r, 500, "Algo salió mal")
    assert "Reintentar" in r.text
    ref = re.search(r"<code>([0-9A-F]{8})</code>", r.text).group(1)
    assert any(ref in m for m in caplog.messages)  # el código queda en los registros
    assert "boom" not in r.text  # no se filtran detalles internos


def test_500_en_fetch_es_json_con_referencia(client):
    r = client.get("/__prueba_errores__/inesperado", headers=JSON)
    assert r.status_code == 500
    assert re.fullmatch(r"[0-9A-F]{8}", r.json()["reference"])


def test_bd_caida_es_503(client):
    r = client.get("/__prueba_errores__/bd", headers=HTML)
    _es_pantalla(r, 503, "Servicio no disponible")
    assert r.headers["Retry-After"] == "5"
    assert "sin conexión" not in r.text


def test_error_de_bd_que_no_es_de_conexion_es_500(client):
    r = client.get("/__prueba_errores__/integridad", headers=HTML)
    _es_pantalla(r, 500, "Algo salió mal")


def test_429_limite_de_intentos(client):
    from app.core.rate_limit import limiter

    limiter.reset()
    try:
        respuestas = [client.get("/keepalive", headers=HTML) for _ in range(31)]
    finally:
        limiter.reset()
    r = respuestas[-1]
    _es_pantalla(r, 429, "Demasiados intentos")
    assert r.headers["Retry-After"] == "60"
