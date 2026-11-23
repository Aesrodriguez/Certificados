from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from sqlalchemy.engine import make_url

# Local Postgres (e.g. Docker) has no SSL; Neon requires it.
_IS_LOCAL_DB = make_url(settings.DATABASE_URL).host in ("localhost", "127.0.0.1")

# Neon's runtime endpoint is PgBouncer in transaction-pooling mode. asyncpg
# already defaults to *anonymous* prepared statements (name=None), which is
# safe through transaction pooling; explicitly naming them (the commonly
# cited PgBouncer workaround) backfires here because the PREPARE and the
# later EXECUTE can land on different pooled backend connections, which is
# exactly what produced InvalidCachedStatementError in testing. We disable
# SQLAlchemy's own prepared-statement object cache (statements are cheap to
# re-describe and a cached PreparedStatement tied to one physical asyncpg
# connection shouldn't be reused across a different one).
#
# Las conexiones se reutilizan entre peticiones (antes NullPool abría una nueva
# conexión TLS a la BD en cada visita, lo que costaba varios viajes de ida y
# vuelta y CPU en cada página). SQLAlchemy siempre trabaja dentro de una
# transacción, así que PgBouncer mantiene cada sentencia en el mismo backend.
# pool_pre_ping descarta conexiones que la BD haya cerrado (p. ej. cuando Neon
# suspende el cómputo) y pool_recycle las renueva cada 5 minutos.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_timeout=30,
    connect_args={
        "ssl": False if _IS_LOCAL_DB else "require",
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
