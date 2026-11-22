"""Sirve las imágenes de marca (cargadas por el admin o las de fábrica)."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_current_session
from app.services import marca_service

router = APIRouter(prefix="/marca", dependencies=[Depends(get_current_session)])

# La URL lleva ?v=<fecha de actualización>, así que se puede guardar en caché.
_CACHE = {"Cache-Control": "private, max-age=86400"}


@router.get("/{clave}")
async def imagen(clave: str, db: AsyncSession = Depends(get_db)):
    if marca_service.ranura(clave) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    fila = await marca_service.obtener(db, clave)
    if fila is not None:
        return Response(content=fila.datos, media_type=fila.content_type, headers=_CACHE)
    return FileResponse(marca_service.archivo_defecto(clave), headers=_CACHE)
