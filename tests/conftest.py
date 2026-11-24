"""Configuración común de los tests.

Se fijan variables de entorno falsas antes de importar la app, para que los tests no
dependan del `.env` local ni toquen la base de datos real (crear el engine no conecta).
"""
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
os.environ["DATABASE_URL_DIRECT"] = ""
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["ENV"] = "development"
for _var in ("GMAIL_SENDER", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
    os.environ[_var] = ""
