import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin


class Servicio(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "servicios"

    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    empresa_key: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    servicio_key: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    lineas: Mapped[list["ServicioLinea"]] = relationship(
        "ServicioLinea",
        back_populates="servicio",
        order_by="ServicioLinea.orden_linea",
        cascade="all, delete-orphan",
    )


class ServicioLinea(Base, UUIDPKMixin):
    __tablename__ = "servicio_lineas"

    servicio_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("servicios.id", ondelete="CASCADE"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(String(300), nullable=False)
    porcentaje: Mapped[float] = mapped_column(Float, nullable=False)
    orden_linea: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    servicio: Mapped["Servicio"] = relationship("Servicio", back_populates="lineas")
