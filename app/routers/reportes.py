"""Historial y reportes estadísticos de certificados."""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import catalogo
from app.core.security import generate_csrf_token
from app.core.templating import templates
from app.db.session import get_db
from app.dependencies.auth import get_current_session, require_role
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.certificate_request import CertificateRequest, StatusEnum
from app.models.session import Session as DbSession
from app.models.user import RoleEnum
from app.services.pdf_service import codigo_documento

router = APIRouter(
    prefix="/reportes",
    dependencies=[Depends(require_role(RoleEnum.ADMIN, RoleEnum.REVISOR))],
)

_TZ = timezone(timedelta(hours=-5))  # Colombia
_ESTADOS = {
    StatusEnum.DRAFT: "Borrador",
    StatusEnum.PENDING: "En revisión",
    StatusEnum.APPROVED: "Aprobado",
    StatusEnum.REJECTED: "Rechazado",
}
_MESES = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _parse_fecha(v: str | None) -> date | None:
    try:
        return date.fromisoformat(v) if v else None
    except ValueError:
        return None


def _rango(desde: date | None, hasta: date | None):
    ini = datetime.combine(desde, time.min, tzinfo=_TZ) if desde else None
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=_TZ) if hasta else None
    return ini, fin


async def _certificados(db: AsyncSession, desde, hasta, empresa, tipo) -> list[CertificateRequest]:
    q = select(CertificateRequest).options(selectinload(CertificateRequest.asesor))
    ini, fin = _rango(desde, hasta)
    if ini:
        q = q.where(CertificateRequest.created_at >= ini)
    if fin:
        q = q.where(CertificateRequest.created_at < fin)
    if empresa:
        q = q.where(CertificateRequest.empresa == empresa)
    if tipo:
        q = q.where(CertificateRequest.tipo_certificado == tipo)
    q = q.order_by(CertificateRequest.created_at.desc())
    return list((await db.execute(q)).scalars().all())


def _items(cert: CertificateRequest) -> list[tuple[str, int]]:
    """(servicio, valor) de cada ítem; para datos antiguos usa nombre_servicio + valor_total."""
    sj = [i for i in (cert.servicios_json or []) if isinstance(i, dict)]
    if any(i.get("servicio") for i in sj):
        return [(str(i.get("servicio")), int(i.get("valor") or 0)) for i in sj if i.get("servicio")]
    if cert.nombre_servicio:
        return [(cert.nombre_servicio, cert.valor_total or 0)]
    return []


def _resumen(certs: list[CertificateRequest]) -> dict:
    por_estado: dict[str, int] = defaultdict(int)
    por_empresa: dict[str, dict] = defaultdict(lambda: {"total": 0, "aprobados": 0, "valor": 0})
    por_tipo: dict[str, dict] = defaultdict(lambda: {"total": 0, "aprobados": 0, "valor": 0})
    por_mes: dict[tuple[int, int], dict] = defaultdict(lambda: {"total": 0, "aprobados": 0, "valor": 0})
    por_servicio: dict[str, dict] = defaultdict(lambda: {"veces": 0, "valor": 0})
    por_asesor: dict[str, int] = defaultdict(int)

    for c in certs:
        aprobado = c.status == StatusEnum.APPROVED
        valor = c.valor_total or 0
        por_estado[_ESTADOS.get(c.status, c.status.value)] += 1
        creado = c.created_at.astimezone(_TZ)
        for clave, tabla in (
            (catalogo.EMPRESAS.get(c.empresa or "", c.empresa or "(sin empresa)"), por_empresa),
            (c.tipo_certificado or "(sin tipo)", por_tipo),
            ((creado.year, creado.month), por_mes),
        ):
            fila = tabla[clave]
            fila["total"] += 1
            if aprobado:
                fila["aprobados"] += 1
                fila["valor"] += valor
        if aprobado:
            for servicio, v in _items(c):
                por_servicio[servicio]["veces"] += 1
                por_servicio[servicio]["valor"] += v
        por_asesor[c.asesor.full_name if c.asesor else "-"] += 1

    aprobados = [c for c in certs if c.status == StatusEnum.APPROVED]
    return {
        "total": len(certs),
        "aprobados": len(aprobados),
        "valor_aprobado": sum(c.valor_total or 0 for c in aprobados),
        "por_estado": sorted(por_estado.items(), key=lambda x: -x[1]),
        "por_empresa": sorted(por_empresa.items(), key=lambda x: -x[1]["total"]),
        "por_tipo": sorted(por_tipo.items(), key=lambda x: -x[1]["total"]),
        "por_mes": [
            (f"{_MESES[m]} {y}", d) for (y, m), d in sorted(por_mes.items(), reverse=True)
        ],
        "por_servicio": sorted(por_servicio.items(), key=lambda x: -x[1]["veces"]),
        "por_asesor": sorted(por_asesor.items(), key=lambda x: -x[1]),
    }


@router.get("")
async def reportes(
    request: Request,
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    empresa: str | None = Query(None),
    tipo: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    session: DbSession = Depends(get_current_session),
):
    d, h = _parse_fecha(desde), _parse_fecha(hasta)
    certs = await _certificados(db, d, h, empresa or None, tipo or None)

    ini, fin = _rango(d, h)
    pdf_q = select(func.count()).select_from(AuditLog).where(
        AuditLog.action == AuditActionEnum.CERT_PDF_GENERATED
    )
    if ini:
        pdf_q = pdf_q.where(AuditLog.created_at >= ini)
    if fin:
        pdf_q = pdf_q.where(AuditLog.created_at < fin)
    pdfs = (await db.execute(pdf_q)).scalar_one()

    tipos = sorted({t for ts in catalogo.TIPOS_POR_EMPRESA.values() for t in ts})
    return templates.TemplateResponse(
        request,
        "reportes.html",
        {
            "current_user": session.user,
            "csrf_token": generate_csrf_token(session.csrf_secret),
            "r": _resumen(certs),
            "pdfs": pdfs,
            "filtros": {"desde": d, "hasta": h, "empresa": empresa or "", "tipo": tipo or ""},
            "empresas": catalogo.EMPRESAS,
            "tipos": tipos,
            "query": request.url.query,
        },
    )


def _celda(v) -> str:
    """Texto seguro para CSV: evita que Excel interprete fórmulas (=, +, -, @)."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


@router.get("/historial.csv")
async def exportar_historial(
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
    empresa: str | None = Query(None),
    tipo: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    certs = await _certificados(
        db, _parse_fecha(desde), _parse_fecha(hasta), empresa or None, tipo or None
    )

    def f(d):
        return d.strftime("%d/%m/%Y") if d else ""

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([
        "N.º documento", "Creado", "Estado", "Empresa", "Tipo de documento",
        "Titular", "CC titular", "Fallecido", "CC fallecido",
        "Fecha del servicio", "Fecha de solicitud", "Fecha de afiliación", "N.º factura",
        "Servicios", "Valor total", "Asesor", "Fecha de aprobación",
    ])
    for c in certs:
        w.writerow([_celda(x) for x in [
            codigo_documento(c),
            c.created_at.astimezone(_TZ).strftime("%d/%m/%Y %H:%M"),
            _ESTADOS.get(c.status, c.status.value),
            catalogo.EMPRESAS.get(c.empresa or "", c.empresa),
            c.tipo_certificado,
            c.cliente_nombre_completo, c.cliente_numero_documento,
            c.fallecido_nombre_completo, c.fallecido_numero_documento,
            f(c.fecha_servicio), f(c.fecha_solicitud_documento), f(c.fecha_afiliacion),
            c.numero_factura,
            " | ".join(s for s, _ in _items(c)),
            c.valor_total or 0,
            c.asesor.full_name if c.asesor else "",
            c.reviewed_at.astimezone(_TZ).strftime("%d/%m/%Y") if c.status == StatusEnum.APPROVED and c.reviewed_at else "",
        ]])

    return Response(
        content=("﻿" + buf.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="historial_certificados.csv"'},
    )
