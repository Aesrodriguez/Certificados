from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Neon's runtime endpoint is PgBouncer in transaction-pooling mode. asyncpg
# already defaults to *anonymous* prepared statements (name=None), which is
# safe through transaction pooling; explicitly naming them (the commonly
# cited PgBouncer workaround) backfires here because the PREPARE and the
# later EXECUTE can land on different pooled backend connections, which is
# exactly what produced InvalidCachedStatementError in testing. We disable
# SQLAlchemy's own prepared-statement object cache (statements are cheap to
# re-describe and a cached PreparedStatement tied to one physical asyncpg
# connection shouldn't be reused across a different one) and use NullPool so
# connection pooling is handled by PgBouncer/Neon, not duplicated here.
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    connect_args={
        "ssl": "require",
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
