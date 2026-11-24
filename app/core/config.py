import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # En Vercel (que define VERCEL=1) el valor por defecto es "production", para que la
    # cookie de sesión salga con `secure` aunque no se configure ENV a mano.
    ENV: str = "production" if os.getenv("VERCEL") else "development"

    DATABASE_URL: str
    # Conexión directa (sin pooler) que usa solo Alembic. La app no la necesita, así que
    # en Vercel puede omitirse; si falta, las migraciones usan DATABASE_URL.
    DATABASE_URL_DIRECT: str = ""

    SESSION_SECRET: str
    SESSION_COOKIE_NAME: str = "clara_session"
    SESSION_LIFETIME_MINUTES: int = 720

    # Gmail API (OAuth2) — usa HTTPS, funciona en Render free tier
    GMAIL_SENDER: str = ""         # tu correo Gmail (ej: andres@gmail.com)
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REFRESH_TOKEN: str = ""

    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_FULL_NAME: str = ""

    # Nombre y cargo que aparecen en la firma del certificado
    FIRMA_NOMBRE: str = ""
    FIRMA_CARGO: str = "Administrador de Ciudad"

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @property
    def gmail_configured(self) -> bool:
        return bool(
            self.GMAIL_SENDER
            and self.GMAIL_CLIENT_ID
            and self.GMAIL_CLIENT_SECRET
            and self.GMAIL_REFRESH_TOKEN
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
