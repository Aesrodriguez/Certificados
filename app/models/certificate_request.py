import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class StatusEnum(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CertificateRequest(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "certificate_requests"

    status: Mapped[StatusEnum] = mapped_column(
        Enum(StatusEnum, name="status_enum"),
        default=StatusEnum.DRAFT,
        nullable=False,
        index=True,
    )
    asesor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    revisor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cliente (parte contratante / familiar)
    cliente_nombre_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    cliente_tipo_documento: Mapped[str] = mapped_column(String(20), nullable=False)
    cliente_numero_documento: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    cliente_telefono: Mapped[str] = mapped_column(String(30), nullable=False)
    cliente_email: Mapped[str] = mapped_column(String(255), nullable=False)
    cliente_direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cliente_ciudad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cliente_parentesco: Mapped[str] = mapped_column(String(100), nullable=False)

    # Fallecido
    fallecido_nombre_completo: Mapped[str] = mapped_column(String(255), nullable=False)
    fallecido_tipo_documento: Mapped[str] = mapped_column(String(20), nullable=False)
    fallecido_numero_documento: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    fallecido_fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    fallecido_fecha_fallecimiento: Mapped[date] = mapped_column(Date, nullable=False)
    fallecido_lugar_fallecimiento: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fallecido_causa_fallecimiento: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fallecido_numero_acta_defuncion: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Metadatos del certificado
    plan_o_poliza: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Campos del dashboard Asesor (basados en el Excel de solicitudes)
    empresa: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tipo_certificado: Mapped[str | None] = mapped_column(String(100), nullable=True)
    numero_aviso: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fecha_afiliacion: Mapped[date | None] = mapped_column(Date, nullable=True)
    numero_recibo_caja: Mapped[str | None] = mapped_column(String(50), nullable=True)
    numero_contrato: Mapped[str | None] = mapped_column(String(100), nullable=True)
    numero_certificado: Mapped[str | None] = mapped_column(String(50), nullable=True)
    numero_factura: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nombre_servicio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    descripcion_servicio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valor_total: Mapped[int | None] = mapped_column(nullable=True)

    asesor: Mapped["User"] = relationship(foreign_keys=[asesor_id])
    revisor: Mapped["User | None"] = relationship(foreign_keys=[revisor_id])
