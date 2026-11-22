"""Imágenes de marca (sello de cancelado, membrete, firma) configurables por el admin.

Si el admin no ha cargado una imagen, se usa la que viene con la aplicación en
app/static/img.
"""

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image as PILImage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.imagen_marca import ImagenMarca

_IMG_DIR = Path(__file__).resolve().parent.parent / "static" / "img"
MAX_BYTES = 3 * 1024 * 1024  # 3 MB
_FORMATOS = {"PNG": "image/png", "JPEG": "image/jpeg"}


@dataclass(frozen=True)
class Ranura:
    clave: str
    titulo: str
    ayuda: str
    defecto: str  # archivo en app/static/img


RANURAS: list[Ranura] = [
    Ranura(
        "sello_cancelado", "Sello de cancelado",
        "Va al lado de la firma en los certificados de gastos por servicios (Recordar).",
        "sello_cancelado.png",
    ),
    Ranura(
        "membrete", "Hoja membretada (logos de encabezado y pie)",
        "Imagen de toda la hoja carta, con el logo arriba y los datos de la empresa abajo.",
        "letterhead.jpg",
    ),
    Ranura(
        "firma", "Firma",
        "Firma escaneada del responsable, preferiblemente PNG con fondo transparente.",
        "signature.png",
    ),
]
_POR_CLAVE = {r.clave: r for r in RANURAS}


class ImagenInvalida(ValueError):
    pass


def ranura(clave: str) -> Ranura | None:
    return _POR_CLAVE.get(clave)


def archivo_defecto(clave: str) -> Path:
    return _IMG_DIR / _POR_CLAVE[clave].defecto


def validar(datos: bytes) -> str:
    """Comprueba que sea una imagen PNG o JPG válida y devuelve su content-type."""
    if not datos:
        raise ImagenInvalida("Selecciona un archivo.")
    if len(datos) > MAX_BYTES:
        raise ImagenInvalida("La imagen no puede pesar más de 3 MB.")
    try:
        with PILImage.open(io.BytesIO(datos)) as img:
            formato = img.format
            img.verify()
    except Exception as exc:
        raise ImagenInvalida("El archivo no es una imagen válida.") from exc
    if formato not in _FORMATOS:
        raise ImagenInvalida("Usa una imagen PNG o JPG.")
    return _FORMATOS[formato]


async def guardadas(db: AsyncSession) -> dict[str, ImagenMarca]:
    filas = (await db.execute(select(ImagenMarca))).scalars().all()
    return {f.clave: f for f in filas}


async def obtener(db: AsyncSession, clave: str) -> ImagenMarca | None:
    return await db.get(ImagenMarca, clave)


async def guardar(db: AsyncSession, clave: str, datos: bytes, nombre: str) -> None:
    content_type = validar(datos)
    fila = await db.get(ImagenMarca, clave)
    if fila is None:
        db.add(ImagenMarca(clave=clave, content_type=content_type, datos=datos,
                           nombre_archivo=nombre[:255]))
    else:
        fila.content_type = content_type
        fila.datos = datos
        fila.nombre_archivo = nombre[:255]
    await db.commit()


async def restablecer(db: AsyncSession, clave: str) -> None:
    fila = await db.get(ImagenMarca, clave)
    if fila is not None:
        await db.delete(fila)
        await db.commit()


async def bytes_para_pdf(db: AsyncSession) -> dict[str, bytes]:
    """Bytes de cada imagen (la cargada o la de fábrica) para dibujarla en el PDF."""
    cargadas = await guardadas(db)
    out: dict[str, bytes] = {}
    for r in RANURAS:
        if r.clave in cargadas:
            out[r.clave] = cargadas[r.clave].datos
        else:
            ruta = _IMG_DIR / r.defecto
            if ruta.exists():
                out[r.clave] = ruta.read_bytes()
    return out


async def urls(db: AsyncSession) -> dict[str, str]:
    """URL de cada imagen para las páginas HTML, con versión para que el navegador
    no muestre una copia vieja después de cambiarla."""
    cargadas = await guardadas(db)
    out = {}
    for r in RANURAS:
        fila = cargadas.get(r.clave)
        v = int(fila.updated_at.timestamp()) if fila else 0
        out[r.clave] = f"/marca/{r.clave}?v={v}"
    return out
