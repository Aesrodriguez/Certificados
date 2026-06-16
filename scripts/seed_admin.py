"""Bootstrap the first Admin user. Safe to re-run: no-ops if the email already exists.

Usage: python -m scripts.seed_admin
Reads ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_FULL_NAME from the environment (.env),
or prompts interactively for any that are missing.
"""

import asyncio
import getpass

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import RoleEnum, User


async def main() -> None:
    email = settings.ADMIN_EMAIL or input("Admin email: ").strip()
    full_name = settings.ADMIN_FULL_NAME or input("Admin full name: ").strip()
    password = settings.ADMIN_PASSWORD or getpass.getpass("Admin password: ")

    if not email or not password or not full_name:
        print("email, full_name y password son obligatorios.")
        return

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"Ya existe un usuario con el correo {email}; no se hizo ningún cambio.")
            return

        admin = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=RoleEnum.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print(f"Usuario Admin creado: {email}")


if __name__ == "__main__":
    asyncio.run(main())
