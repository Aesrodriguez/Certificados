import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.servicio import Servicio, ServicioLinea


async def list_servicios(db: AsyncSession) -> list[Servicio]:
    result = await db.execute(
        select(Servicio)
        .options(selectinload(Servicio.lineas))
        .order_by(Servicio.orden)
    )
    return list(result.scalars().all())


async def get_servicio(db: AsyncSession, servicio_id: uuid.UUID) -> Servicio | None:
    result = await db.execute(
        select(Servicio)
        .where(Servicio.id == servicio_id)
        .options(selectinload(Servicio.lineas))
    )
    return result.scalar_one_or_none()


async def create_servicio(
    db: AsyncSession,
    *,
    nombre: str,
    empresa_key: str,
    servicio_key: str,
    orden: int,
    is_active: bool,
    lineas: list[tuple[str, float]],
) -> Servicio:
    svc = Servicio(
        nombre=nombre,
        empresa_key=empresa_key,
        servicio_key=servicio_key,
        orden=orden,
        is_active=is_active,
    )
    db.add(svc)
    await db.flush()

    for i, (lin_nombre, lin_pct) in enumerate(lineas):
        db.add(ServicioLinea(
            servicio_id=svc.id,
            nombre=lin_nombre,
            porcentaje=lin_pct,
            orden_linea=i,
        ))

    await db.commit()
    await db.refresh(svc)
    return svc


async def update_servicio(
    db: AsyncSession,
    svc: Servicio,
    *,
    nombre: str,
    empresa_key: str,
    servicio_key: str,
    orden: int,
    is_active: bool,
    lineas: list[tuple[str, float]],
) -> Servicio:
    svc.nombre = nombre
    svc.empresa_key = empresa_key
    svc.servicio_key = servicio_key
    svc.orden = orden
    svc.is_active = is_active

    for linea in list(svc.lineas):
        await db.delete(linea)
    await db.flush()

    for i, (lin_nombre, lin_pct) in enumerate(lineas):
        db.add(ServicioLinea(
            servicio_id=svc.id,
            nombre=lin_nombre,
            porcentaje=lin_pct,
            orden_linea=i,
        ))

    await db.commit()
    await db.refresh(svc)
    return svc


async def delete_servicio(db: AsyncSession, svc: Servicio) -> None:
    await db.delete(svc)
    await db.commit()


async def get_lineas_for_cert(
    db: AsyncSession,
    empresa: str | None,
    nombre_servicio: str | None,
    valor_total: int,
    servicios_json: list | None = None,
) -> list[tuple[str, int]]:
    """DB-backed service breakdown lookup, falls back to hardcoded if no match.

    If servicios_json contains explicit line items they are returned directly
    without any template lookup.
    """
    if servicios_json:
        result_lines = []
        for item in servicios_json:
            if isinstance(item, dict) and "nombre" in item and "valor" in item:
                result_lines.append((str(item["nombre"]), int(item["valor"])))
        if result_lines:
            return result_lines
    try:
        result = await db.execute(
            select(Servicio)
            .where(Servicio.is_active.is_(True))
            .options(selectinload(Servicio.lineas))
            .order_by(Servicio.orden)
        )
        servicios = list(result.scalars().all())
    except Exception:
        servicios = []

    emp = (empresa or "").lower()
    svc_name = (nombre_servicio or "").lower()

    for svc in servicios:
        if svc.empresa_key in emp and svc.servicio_key in svc_name:
            lineas_sorted = sorted(svc.lineas, key=lambda l: l.orden_linea)
            calculadas: list[tuple[str, int]] = [
                (l.nombre, round(valor_total * l.porcentaje)) for l in lineas_sorted
            ]
            diff = valor_total - sum(v for _, v in calculadas)
            if diff and calculadas:
                idx = max(range(len(calculadas)), key=lambda i: calculadas[i][1])
                nom, val = calculadas[idx]
                calculadas[idx] = (nom, val + diff)
            return calculadas

    from app.services.pdf_service import get_lineas_servicio
    return get_lineas_servicio(empresa, nombre_servicio, valor_total)
