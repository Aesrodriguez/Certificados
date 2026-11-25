from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ImagenMarca(Base):
    """Imágenes que el admin carga en Configuración (sello, membrete, firma).

    Se guardan en la BD porque en Vercel el disco es de solo lectura y no persiste.
    """

    __tablename__ = "imagenes_marca"

    clave: Mapped[str] = mapped_column(String(50), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    datos: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
