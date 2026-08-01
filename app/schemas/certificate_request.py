from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

TipoDocumento = Literal["CC", "CE", "TI", "PAS", "RC"]

TIPOS_CERTIFICADO = [
    "CERTIFICADO DE GASTOS RECORDAR",
    "CERTIFICACION DE GASTOS POR FACTURA",
    "CERTIFICADO DE ELEMENTOS DETALLADO",
    "CERTIFICADO DE ELEMENTOS PARA SUCESION",
    "CERTIFICADO DE ELEMENTOS SENCILLO",
]

EMPRESAS = ["RECORDAR", "PARQUES Y FUNERARIAS"]

# Servicios por empresa — el fragmento en minúsculas debe coincidir con
# la lógica de get_lineas_servicio en pdf_service.py
SERVICIOS_RECORDAR = [
    "SERVICIO FUNERARIO CON TRANSPORTE, VELACIÓN Y MISA",
    "SERVICIO FUNERARIO CON TRANSPORTE Y VELACIÓN",
    "SERVICIO FUNERARIO",
]

SERVICIOS_PYF = [
    "SERVICIO FUNERARIO CREMACIÓN",
    "SERVICIO FUNERARIO GRAN EXTRA",
    "SERVICIO FUNERARIO ESTILO J",
    "SERVICIO FUNERARIO ESTILO K",
    "SERVICIO FUNERARIO ESTILO L",
    "SERVICIO FUNERARIO ESTÁNDAR",
]

TODOS_LOS_SERVICIOS = SERVICIOS_RECORDAR + [
    s for s in SERVICIOS_PYF if s not in SERVICIOS_RECORDAR
]


class CertificateRequestIn(BaseModel):
    # Datos del certificado
    tipo_certificado: str | None = Field(default=None, max_length=100)
    empresa: str | None = Field(default=None, max_length=100)
    numero_certificado: str | None = Field(default=None, max_length=50)

    # Cliente (solicitante)
    cliente_nombre_completo: str = Field(min_length=1, max_length=255)
    cliente_tipo_documento: TipoDocumento
    cliente_numero_documento: str = Field(min_length=1, max_length=30)
    cliente_telefono: str = Field(min_length=1, max_length=30)
    cliente_email: EmailStr
    cliente_direccion: str | None = Field(default=None, max_length=255)
    cliente_ciudad: str | None = Field(default=None, max_length=100)
    cliente_parentesco: str = Field(min_length=1, max_length=100)

    # Fallecido
    fallecido_nombre_completo: str = Field(min_length=1, max_length=255)
    fallecido_tipo_documento: TipoDocumento
    fallecido_numero_documento: str = Field(min_length=1, max_length=30)
    fallecido_fecha_nacimiento: date | None = None
    fallecido_fecha_fallecimiento: date
    fallecido_lugar_fallecimiento: str | None = Field(default=None, max_length=255)
    fallecido_causa_fallecimiento: str | None = Field(default=None, max_length=255)
    fallecido_numero_acta_defuncion: str | None = Field(default=None, max_length=50)

    # Servicios utilizados
    nombre_servicio: str | None = Field(default=None, max_length=255)
    descripcion_servicio: str | None = Field(default=None, max_length=255)
    valor_total: int | None = None

    # Datos administrativos
    numero_aviso: str | None = Field(default=None, max_length=50)
    fecha_afiliacion: date | None = None
    numero_recibo_caja: str | None = Field(default=None, max_length=50)
    numero_contrato: str | None = Field(default=None, max_length=100)
    numero_factura: str | None = Field(default=None, max_length=50)

    # Metadatos
    plan_o_poliza: str | None = Field(default=None, max_length=100)
    observaciones: str | None = None

    @field_validator("fallecido_fecha_nacimiento", mode="before")
    @classmethod
    def nacimiento_no_futuro(cls, v):
        if v is None or v == "":
            return None
        d = v if isinstance(v, date) else date.fromisoformat(str(v))
        if d > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura.")
        return d

    @field_validator("fallecido_fecha_fallecimiento", mode="before")
    @classmethod
    def fallecimiento_no_futuro(cls, v):
        if v is None or v == "":
            raise ValueError("La fecha de fallecimiento es obligatoria.")
        d = v if isinstance(v, date) else date.fromisoformat(str(v))
        if d > date.today():
            raise ValueError("La fecha de fallecimiento no puede ser futura.")
        return d
