from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appsetting import AppSetting


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
