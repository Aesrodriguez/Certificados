import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditActionEnum(str, enum.Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    USER_CREATED = "user_created"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_DISABLED = "user_disabled"
    USER_ENABLED = "user_enabled"
    CERT_CREATED = "cert_created"
    CERT_UPDATED = "cert_updated"
    CERT_SUBMITTED = "cert_submitted"
    CERT_VIEWED = "cert_viewed"
    CERT_APPROVED = "cert_approved"
    CERT_REJECTED = "cert_rejected"
    CERT_PDF_GENERATED = "cert_pdf_generated"
    CERT_EMAIL_SENT = "cert_email_sent"
    CERT_EMAIL_FAILED = "cert_email_failed"


class AuditLog(Base, UUIDPKMixin):
    __tablename__ = "audit_logs"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[AuditActionEnum] = mapped_column(
        Enum(AuditActionEnum, name="audit_action_enum"), nullable=False, index=True
    )
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    actor: Mapped["User | None"] = relationship()
