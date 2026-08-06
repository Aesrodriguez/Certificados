import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
