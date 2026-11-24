import os
from collections.abc import AsyncGenerator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from sqlalchemy.engine import make_url

# Local Postgres (e.g. Docker) has no SSL; Neon requires it.
_IS_LOCAL_DB = make_url(settings.DATABASE_URL).host in ("localhost", "127.0.0.1")

# El pooler (Supabase, puerto 6543) está en modo transacción: varias conexiones de
# la app comparten los mismos backends de Postgres. Aunque SQLAlchemy pase
# name=None, asyncpg nombra cada prepared statement en orden por conexión
# (__asyncpg_stmt_1__, _2__…), así que dos conexiones que caen en el mismo backend
# chocan con DuplicatePreparedStatementError. Con nombres únicos (uuid4) no hay
# choque; es la solución que documenta SQLAlchemy para PgBouncer. PREPARE y
# EXECUTE van dentro de la misma transacción, así que llegan al mismo backend.
# También se desactivan las cachés de statements de asyncpg y de SQLAlchemy,
# para no reutilizar un statement preparado en otro backend.
#
# Las conexiones se reutilizan entre peticiones (antes NullPool abría una nueva
# conexión TLS a la BD en cada visita, lo que costaba varios viajes de ida y
# vuelta y CPU en cada página). SQLAlchemy siempre trabaja dentro de una
# transacción, así que PgBouncer mantiene cada sentencia en el mismo backend.
# pool_pre_ping descarta conexiones que la BD haya cerrado (p. ej. cuando Neon
# suspende el cómputo) y pool_recycle las renueva cada 5 minutos.
_CONNECT_ARGS = {
    "ssl": False if _IS_LOCAL_DB else "require",
    "statement_cache_size": 0,
    "prepared_statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
}

# En Vercel (funciones serverless) la instancia se congela entre peticiones y
# las conexiones guardadas en un pool quedan muertas; ahí se abre una conexión
# por petición contra el pooler de Supabase (puerto 6543), que es quien
# mantiene las conexiones reales a Postgres. Vercel define VERCEL=1.
if os.getenv("VERCEL"):
    engine = create_async_engine(
        settings.DATABASE_URL, poolclass=NullPool, connect_args=_CONNECT_ARGS
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_timeout=30,
        connect_args=_CONNECT_ARGS,
    )
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
