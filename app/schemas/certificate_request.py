from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, ValidationInfo, field_validator


class ServicioLineaIn(BaseModel):
    # servicio: opción elegida del catálogo (None en certificados antiguos con líneas manuales)
    servicio: str | None = Field(default=None, max_length=300)
    nombre: str = Field(min_length=1, max_length=300)
    valor: int = Field(ge=0, le=2_000_000_000)


TipoDocumento = Literal["CC", "CE", "TI", "PAS", "RC"]


def _fecha_no_futura(v, mensaje: str):
    if v is None or v == "":
        return None
    d = v if isinstance(v, date) else date.fromisoformat(str(v))
    if d > date.today():
        raise ValueError(mensaje)
    return d


class CertificateRequestIn(BaseModel):
    # Datos del certificado
    tipo_certificado: str | None = Field(default=None, max_length=100)
    empresa: str | None = Field(default=None, max_length=100)
    numero_certificado: str | None = Field(default=None, max_length=50)

    # Cliente (solicitante)
    cliente_nombre_completo: str = Field(min_length=1, max_length=255)
    cliente_tipo_documento: TipoDocumento
    cliente_numero_documento: str = Field(min_length=1, max_length=30)
    cliente_telefono: str | None = Field(default=None, max_length=30)
    cliente_email: EmailStr | None = None
    cliente_direccion: str | None = Field(default=None, max_length=255)
    cliente_ciudad: str | None = Field(default=None, max_length=100)
    cliente_parentesco: str | None = Field(default=None, max_length=100)

    # Fallecido
    fallecido_nombre_completo: str = Field(min_length=1, max_length=255)
    fallecido_tipo_documento: TipoDocumento
    fallecido_numero_documento: str = Field(min_length=1, max_length=30)
    fallecido_fecha_nacimiento: date | None = None
    fallecido_fecha_fallecimiento: date | None = None
    fallecido_lugar_fallecimiento: str | None = Field(default=None, max_length=255)
    fallecido_causa_fallecimiento: str | None = Field(default=None, max_length=255)
    fallecido_numero_acta_defuncion: str | None = Field(default=None, max_length=50)

    # Servicios utilizados
    nombre_servicio: str | None = Field(default=None, max_length=255)
    descripcion_servicio: str | None = Field(default=None, max_length=255)
    valor_total: int | None = Field(default=None, ge=0, le=2_000_000_000)

    # Metadatos del certificado
    # Orden importante: cada validador de orden de fechas lee en info.data las fechas declaradas antes
    fecha_servicio: date | None = None
    fecha_solicitud_documento: date | None = None

    # Datos administrativos
    numero_aviso: str | None = Field(default=None, max_length=50)
    fecha_afiliacion: date | None = None
    numero_recibo_caja: str | None = Field(default=None, max_length=50)
    numero_contrato: str | None = Field(default=None, max_length=100)
    numero_factura: str | None = Field(default=None, max_length=50)

    # Metadatos
    plan_o_poliza: str | None = Field(default=None, max_length=100)
    observaciones: str | None = Field(default=None, max_length=2000)
    servicios_json: list[ServicioLineaIn] | None = Field(default=None, max_length=50)

    @field_validator("cliente_email", "cliente_telefono", "cliente_parentesco", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("fallecido_fecha_nacimiento", mode="before")
    @classmethod
    def nacimiento_no_futuro(cls, v):
        return _fecha_no_futura(v, "La fecha de nacimiento no puede ser futura.")

    @field_validator("fecha_solicitud_documento", mode="before")
    @classmethod
    def solicitud_no_futura(cls, v):
        return _fecha_no_futura(v, "La fecha de solicitud no puede ser futura.")

    @field_validator("fecha_servicio", mode="before")
    @classmethod
    def servicio_no_futuro(cls, v):
        return _fecha_no_futura(v, "La fecha del servicio no puede ser futura.")

    @field_validator("fecha_afiliacion", mode="before")
    @classmethod
    def afiliacion_no_futura(cls, v):
        return _fecha_no_futura(v, "La fecha de afiliación no puede ser futura.")

    @field_validator("fallecido_fecha_fallecimiento", mode="before")
    @classmethod
    def fallecimiento_no_futuro(cls, v):
        return _fecha_no_futura(v, "La fecha de fallecimiento no puede ser futura.")

    @field_validator("fallecido_fecha_fallecimiento", mode="after")
    @classmethod
    def fallecimiento_despues_de_nacimiento(cls, v, info: ValidationInfo):
        # fallecido_fecha_nacimiento se declara antes, así que ya está validada en info.data
        nacimiento = info.data.get("fallecido_fecha_nacimiento")
        if v and nacimiento and v < nacimiento:
            raise ValueError("La fecha de fallecimiento no puede ser anterior a la de nacimiento.")
        return v

    @field_validator("fecha_servicio", mode="after")
    @classmethod
    def servicio_despues_de_fallecimiento(cls, v, info: ValidationInfo):
        fallecimiento = info.data.get("fallecido_fecha_fallecimiento")
        if v and fallecimiento and v < fallecimiento:
            raise ValueError("La fecha del servicio no puede ser anterior a la de fallecimiento.")
        return v

    @field_validator("fecha_solicitud_documento", mode="after")
    @classmethod
    def solicitud_despues_de_servicio(cls, v, info: ValidationInfo):
        servicio = info.data.get("fecha_servicio")
        if v and servicio and v < servicio:
            raise ValueError("La fecha de solicitud no puede ser anterior a la del servicio.")
        return v
