import asyncpg

_pool: asyncpg.Pool | None = None

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS calendar_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id UUID NOT NULL,
    nylas_grant_id TEXT NOT NULL,
    google_email TEXT,
    connected_at TIMESTAMPTZ DEFAULT now(),
    is_valid BOOLEAN DEFAULT true
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cc_owner ON calendar_connections(owner_id);
"""


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool not initialised – call init_pool() first")
    return _pool


async def init_pool(dsn: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
