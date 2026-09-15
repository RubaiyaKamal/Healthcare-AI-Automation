import asyncpg
from contextlib import asynccontextmanager
from config import DATABASE_URL


_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """Create the shared connection pool. Call once at app startup."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn():
    assert _pool is not None, "database pool not initialized — call init_pool() first"
    async with _pool.acquire() as conn:
        yield conn


async def query(sql: str, *args):
    async with get_conn() as conn:
        return await conn.fetch(sql, *args)


async def query_one(sql: str, *args):
    async with get_conn() as conn:
        return await conn.fetchrow(sql, *args)


async def execute(sql: str, *args) -> str:
    async with get_conn() as conn:
        return await conn.execute(sql, *args)