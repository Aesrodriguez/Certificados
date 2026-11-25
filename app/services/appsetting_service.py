import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import catalogo
from app.models.appsetting import AppSetting

# Fields the admin can toggle as required/optional.
# Tuple: (field_name, human-readable label, section)
CONFIGURABLE_FIELDS: list[tuple[str, str, str]] = [
    ("cliente_email",                  "Correo electrónico",        "solicitante"),
    ("cliente_telefono",               "Teléfono",                  "solicitante"),
    ("cliente_parentesco",             "Parentesco con el fallecido","solicitante"),
    ("cliente_direccion",              "Dirección",                  "solicitante"),
    ("cliente_ciudad",                 "Ciudad",                     "solicitante"),
    ("fallecido_fecha_nacimiento",     "Fecha de nacimiento",        "fallecido"),
    ("fallecido_lugar_fallecimiento",  "Lugar de fallecimiento",     "fallecido"),
    ("fallecido_causa_fallecimiento",  "Causa de fallecimiento",     "fallecido"),
    ("fallecido_numero_acta_defuncion","N.° acta de defunción",      "fallecido"),
]

_VALID_CONFIGURABLE = {f for f, _, _ in CONFIGURABLE_FIELDS}
_DEFAULT_REQUIRED: set[str] = {"cliente_email"}


async def get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else default


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    await db.commit()


async def get_required_fields(db: AsyncSession) -> set[str]:
    raw = await get_setting(db, "required_fields", default="")
    if not raw:
        return set(_DEFAULT_REQUIRED)
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return set(_DEFAULT_REQUIRED)
        return set(parsed)
    except (json.JSONDecodeError, TypeError):
        return set(_DEFAULT_REQUIRED)


async def set_required_fields(db: AsyncSession, fields: list[str]) -> None:
    cleaned = sorted(f for f in fields if f in _VALID_CONFIGURABLE)
    await set_setting(db, "required_fields", json.dumps(cleaned))


# ── Formato del certificado ──────────────────────────────────────────────────
# Tipos de certificado que llevan el sello de CAJA CANCELADO. Por defecto solo el
# de gastos por servicio (RECORDAR), como dice la especificación; el admin puede
# añadir otros desde Configuración.
SELLO_TIPOS_DEFECTO: tuple[str, ...] = (catalogo.TIPO_SERVICIOS,)
SEDE_DEFECTO = "Barranquilla"


@dataclass(frozen=True)
class FormatoCertificado:
    sello_tipos: frozenset[str] = frozenset(SELLO_TIPOS_DEFECTO)
    sede: str = SEDE_DEFECTO


def _tipos_validos() -> list[str]:
    vistos: list[str] = []
    for tipos in catalogo.TIPOS_POR_EMPRESA.values():
        vistos.extend(t for t in tipos if t not in vistos)
    return vistos


TIPOS_CERTIFICADO: list[str] = _tipos_validos()


async def get_formato(db: AsyncSession) -> FormatoCertificado:
    raw = await get_setting(db, "sello_tipos", default="")
    try:
        tipos = json.loads(raw) if raw else list(SELLO_TIPOS_DEFECTO)
        if not isinstance(tipos, list):
            tipos = list(SELLO_TIPOS_DEFECTO)
    except (json.JSONDecodeError, TypeError):
        tipos = list(SELLO_TIPOS_DEFECTO)
    sede = (await get_setting(db, "sede", default="")).strip() or SEDE_DEFECTO
    return FormatoCertificado(sello_tipos=frozenset(tipos), sede=sede)


async def set_formato(db: AsyncSession, sello_tipos: list[str], sede: str) -> None:
    validos = set(TIPOS_CERTIFICADO)
    await set_setting(db, "sello_tipos", json.dumps(sorted(t for t in sello_tipos if t in validos)))
    await set_setting(db, "sede", sede.strip()[:100] or SEDE_DEFECTO)
