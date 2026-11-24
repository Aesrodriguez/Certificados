import pytest

from app.core.config import Settings

BASE = {"SESSION_SECRET": "x"}


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **{**BASE, **kwargs})


@pytest.mark.parametrize(
    "vercel, esperado",
    [(None, "development"), ("1", "production")],
)
def test_env_por_defecto_segun_vercel(monkeypatch, vercel, esperado):
    # El valor por defecto de ENV se calcula al definir la clase, así que se recarga.
    import importlib

    import app.core.config as config

    monkeypatch.delenv("ENV", raising=False)
    if vercel:
        monkeypatch.setenv("VERCEL", vercel)
    else:
        monkeypatch.delenv("VERCEL", raising=False)
    config = importlib.reload(config)
    try:
        s = config.Settings(_env_file=None, DATABASE_URL="postgresql+asyncpg://u:p@h/db", **BASE)
        assert s.ENV == esperado
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_database_url_direct_es_opcional():
    s = _settings(DATABASE_URL="postgresql+asyncpg://u:p@h/db")
    assert s.DATABASE_URL_DIRECT == ""


def test_migration_url_usa_la_directa_si_existe():
    s = _settings(
        DATABASE_URL="postgresql+asyncpg://u:p@pooler:6543/db?ssl=require",
        DATABASE_URL_DIRECT="postgresql+psycopg2://u:p@directa:5432/db?sslmode=require",
    )
    assert s.migration_url == "postgresql+psycopg2://u:p@directa:5432/db?sslmode=require"


def test_migration_url_adapta_la_de_la_app_al_driver_sync():
    s = _settings(DATABASE_URL="postgresql+asyncpg://u:p@pooler:6543/db?ssl=require")
    assert s.migration_url == "postgresql+psycopg2://u:p@pooler:6543/db?sslmode=require"


def test_migration_url_no_duplica_sslmode_existente():
    s = _settings(DATABASE_URL="postgresql+asyncpg://u:p@h/db?sslmode=require")
    assert s.migration_url == "postgresql+psycopg2://u:p@h/db?sslmode=require"
