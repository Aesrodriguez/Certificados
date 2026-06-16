from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "development"

    DATABASE_URL: str
    DATABASE_URL_DIRECT: str

    SESSION_SECRET: str
    SESSION_COOKIE_NAME: str = "clara_session"
    SESSION_LIFETIME_MINUTES: int = 720

    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Clara Certificados <certificados@example.com>"

    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_FULL_NAME: str = ""

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
