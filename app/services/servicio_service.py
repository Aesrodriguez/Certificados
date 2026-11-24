import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.catalogo import destino_final, discrimina, norm
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


def _repartir(valor_total: int, plantilla: list[tuple[str, float]]) -> list[tuple[str, int]]:
    """Aplica porcentajes y corrige el redondeo sobre el ítem de mayor valor."""
    calculadas = [(nombre, round(valor_total * pct)) for nombre, pct in plantilla]
    diff = valor_total - sum(v for _, v in calculadas)
    if diff and calculadas:
        idx = max(range(len(calculadas)), key=lambda i: calculadas[i][1])
        nom, val = calculadas[idx]
        calculadas[idx] = (nom, val + diff)
    return calculadas


async def _plantillas_activas(db: AsyncSession) -> list[Servicio]:
    try:
        result = await db.execute(
            select(Servicio)
            .where(Servicio.is_active.is_(True))
            .options(selectinload(Servicio.lineas))
            .order_by(Servicio.orden)
        )
        return list(result.scalars().all())
    except Exception:
        return []


def _desglosar(
    plantillas: list[Servicio], empresa: str | None, servicio: str | None, valor: int
) -> list[tuple[str, int]]:
    """Busca la primera plantilla de BD que coincida (sin tildes); si no, la fija del código."""
    emp = norm(empresa)
    svc_name = norm(servicio)
    for svc in plantillas:
        if norm(svc.empresa_key) in emp and norm(svc.servicio_key) in svc_name:
            lineas_sorted = sorted(svc.lineas, key=lambda l: l.orden_linea)
            return _repartir(valor, [(l.nombre, l.porcentaje) for l in lineas_sorted])

    from app.services.pdf_service import get_lineas_servicio
    return get_lineas_servicio(empresa, servicio, valor)


async def get_lineas_for_cert(
    db: AsyncSession,
    empresa: str | None,
    nombre_servicio: str | None,
    valor_total: int,
    servicios_json: list | None = None,
) -> list[tuple[str, int]]:
    """Desglose plano de un solo servicio (usado por /api/lineas).

    Si servicios_json trae líneas explícitas (formato antiguo) se devuelven tal cual.
    """
    if servicios_json:
        result_lines = [
            (str(i["nombre"]), int(i["valor"]))
            for i in servicios_json
            if isinstance(i, dict) and "nombre" in i and "valor" in i
        ]
        if result_lines:
            return result_lines
    return _desglosar(await _plantillas_activas(db), empresa, nombre_servicio, valor_total)


async def build_desglose(db: AsyncSession, cert) -> tuple[list[dict], str | None]:
    """Arma los grupos de líneas que van en el certificado y la leyenda de destino final.

    Cada grupo: {"titulo": str | None, "valor": int, "lineas": [(nombre, valor), ...]}.
    `titulo` es el producto o servicio prestado (p. ej. "SERVICIO FUNERARIO ESTILO L") y
    va en negrilla con su valor, encabezando las líneas del desglose.

    Formatos de servicios_json soportados:
      - Nuevo: [{"servicio", "nombre", "valor"}] — un ítem por servicio seleccionado.
      - Antiguo: [{"nombre", "valor"}] — líneas ya desglosadas a mano.
      - Vacío: se desglosa nombre_servicio + valor_total con la plantilla.
    """
    items = [i for i in (cert.servicios_json or []) if isinstance(i, dict)]
    nuevos = [i for i in items if i.get("servicio")]
    grupos: list[dict] = []

    if nuevos:
        plantillas = await _plantillas_activas(db)
        for it in nuevos:
            servicio = str(it.get("servicio") or "")
            nombre = str(it.get("nombre") or servicio)
            valor = int(it.get("valor") or 0)
            if discrimina(cert.empresa, servicio) and valor > 0:
                lineas = _desglosar(plantillas, cert.empresa, servicio, valor)
                grupos.append({"titulo": nombre, "valor": valor, "lineas": lineas})
            else:
                grupos.append({"titulo": None, "valor": valor, "lineas": [(nombre, valor)]})
        destino = destino_final([str(i.get("servicio") or "") for i in nuevos])
    elif items:
        lineas = [(str(i["nombre"]), int(i["valor"])) for i in items if "nombre" in i and "valor" in i]
        grupos.append({"titulo": None, "valor": sum(v for _, v in lineas), "lineas": lineas})
        destino = destino_final([cert.nombre_servicio or ""])
    elif cert.valor_total:
        lineas = _desglosar(await _plantillas_activas(db), cert.empresa, cert.nombre_servicio, cert.valor_total)
        grupos.append({"titulo": None, "valor": cert.valor_total, "lineas": lineas})
        destino = destino_final([cert.nombre_servicio or ""])
    else:
        destino = destino_final([cert.nombre_servicio or ""])

    # El título de cada grupo es el producto o servicio prestado y encabeza su desglose.
    # Si el grupo no tiene título (formatos antiguos), se usa el nombre del servicio.
    for g in grupos:
        if not g["titulo"] and len(g["lineas"]) > 1:
            g["titulo"] = cert.nombre_servicio or None
        # Si el desglose es una sola línea igual al producto, no se repite.
        if g["titulo"] and len(g["lineas"]) == 1 and g["lineas"][0][0] == g["titulo"]:
            g["titulo"] = None
    return grupos, destino
